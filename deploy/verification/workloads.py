"""Private in-cluster smoke test. Emit only counts, event IDs and boolean checks."""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from wonderland_events.transport import Event, aws_client


@dataclass
class Response:
    status_code: int
    body: bytes

    def json(self):
        return json.loads(self.body)


def get(url):
    # Keep the verification Job compatible with the production image's dependencies.
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return Response(response.status, response.read())
    except urllib.error.HTTPError as response:
        return Response(response.code, response.read())


def verify():
    engines = {s: create_engine(os.environ[f'{s.upper()}_DATABASE_URL'], pool_size=1, max_overflow=0,
                               hide_parameters=True, connect_args={'connect_timeout': 5}) for s in ['catalog', 'booking']}
    checks = {}
    for service in ['catalog', 'booking', 'payment', 'admission']:
        response = get(f'http://wonderland-{service}:8000/health/ready')
        checks[f'{service}_ready'] = response.status_code == 200
    for service in ['catalog', 'booking', 'payment', 'admission']:
        # Select declared read-only protected routes; never submit bookings or payments.
        schema = get(f'http://wonderland-{service}:8000/openapi.json').json()
        protected = [p for p, methods in schema['paths'].items() if 'get' in methods and methods['get'].get('security')]
        assert protected, 'Expected protected API routes'
        path = next((p for p in protected if '{' not in p), protected[0])
        path = re.sub(r'\{([^}]+)\}', lambda m: 'MOCK-' + '0'*32 if m[1] == 'reference' else '00000000-0000-0000-0000-000000000000', path)
        checks[f'{service}_unauthenticated_denied'] = get(f'http://wonderland-{service}:8000{path}').status_code in [401, 403]
    expected, actual = {}, {}
    for attempt in range(45):
        with engines['catalog'].connect() as connection:
            rows = connection.execute(text('''SELECT t.id,t.code,t.name,t.min_guests,t.max_guests,t.active,
              p.amount_minor,p.currency,p.version FROM catalog.ticket_tiers t JOIN catalog.ticket_prices p ON p.tier_id=t.id WHERE p.active''')).mappings().all()
            expected = {str(r['id']): dict(id=str(r['id']), code=r['code'], name=r['name'], min_guests=r['min_guests'], max_guests=r['max_guests'], active=r['active'], amount_minor=r['amount_minor'], currency=r['currency'], price_version=r['version']) for r in rows}
        with engines['booking'].connect() as connection:
            actual = {str(r[0]): r[1] for r in connection.execute(text('SELECT tier_id,payload FROM booking.ticket_price_projection'))}
        if len(expected) >= 4 and expected == actual:
            break
        time.sleep(2)
    checks['pricing_projection_matches_catalog'] = len(expected) >= 4 and expected == actual
    for service, engine in engines.items():
        with engine.connect() as connection:
            checks[f'{service}_tls'] = connection.scalar(text('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')) is True
    with engines['catalog'].connect() as connection:
        row = connection.execute(text('SELECT * FROM catalog.outbox_events WHERE published_at IS NOT NULL ORDER BY created_at DESC,id LIMIT 1')).mappings().one()
        event = Event(event_id=row['id'], source='catalog', event_type=row['event_type'], aggregate_id=row['aggregate_id'], aggregate_version=row['aggregate_version'], occurred_at=row['created_at'], data=row['payload'])
    client = aws_client('sns', 'ap-south-1')
    for _ in range(2):
        client.publish(TopicArn=os.environ['CATALOG_TOPIC_ARN'], Message=event.model_dump_json())
    # Commit-before-ack/inbox deduplication must retain one row for the repeated event ID.
    time.sleep(8)
    with engines['booking'].connect() as connection:
        checks['duplicate_event_has_one_inbox_row'] = connection.scalar(text("SELECT count(*) FROM booking.event_inbox WHERE consumer='booking-prices-v1' AND event_id=:id"), dict(id=event.event_id)) == 1
    if not all(checks.values()):
        print('WORKLOAD_CHECKS=' + json.dumps(checks, sort_keys=True), flush=True)
        raise AssertionError('Smoke verification failed')
    return dict(status='VERIFIED', checks=checks, synchronized_tiers=len(expected), duplicate_event_id=str(event.event_id), checkout='mock', secrets_logged=False)


if __name__ == '__main__':
    try:
        print('WORKLOAD_REPORT=' + json.dumps(verify(), sort_keys=True), flush=True)
    except Exception as error:
        print('WORKLOAD_VERIFICATION_FAILED=' + type(error).__name__, flush=True)
        sys.exit(1)
