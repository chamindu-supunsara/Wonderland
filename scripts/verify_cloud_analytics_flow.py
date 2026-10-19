"""Reconcile real mock before/after facts; do not infer provider revenue or occupancy."""
import json
from datetime import datetime, timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1]
read=lambda name:json.loads((root/'docs/evidence'/name).read_text(encoding='utf-8-sig'))
before=read('step10e-analytics-before.json')['facts']
after=read('step10e-analytics-after.json')['facts']
b=before['pipeline'][0];a=after['pipeline'][0]
rides=after['popular_rides']
grid=after['hourly_activity']
inbox_before={r['consumer']:r['processed_events'] for r in before['inbox']}
inbox_after={r['consumer']:r['processed_events'] for r in after['inbox']}
checks={
 'one_new_arrival':a['total_guest_arrivals']-b['total_guest_arrivals']==1,
 'two_intentional_new_rides':a['total_ride_uses']-b['total_ride_uses']==2,
 'one_guest_two_rides_reconciled':len(rides)==1 and rides[0]['attraction_name']=='Wonder Quest' and rides[0]['ride_uses']==2 and rides[0]['unique_guests']==1,
 'no_unmatched_rides':a['rides_awaiting_arrival']==0,
 'exact_three_admission_events_despite_duplicate_http_checkin':inbox_after.get('analytics-admissions-v1',0)-inbox_before.get('analytics-admissions-v1',0)==3,
 'confirmation_purchases_unchanged_by_visits':after['purchases']==before['purchases'],
 'two_real_mock_confirmations_eighty_simulated_dollars':after['purchases'][0]['purchases']==2 and after['purchases'][0]['simulated_revenue_minor']==8000 and after['purchases'][0]['mode']=='MOCK',
 'colombo_date_and_all_24_hours':len(grid)==24 and {r['visit_date'] for r in grid}=={'2026-10-19'} and {r['hour_of_day'] for r in grid}==set(range(24)),
 'nine_am_arrival_and_first_ride':any(r['hour_of_day']==9 and r['guest_arrivals']==1 and r['ride_uses']==1 for r in grid),
 'ten_am_second_ride':any(r['hour_of_day']==10 and r['guest_arrivals']==0 and r['ride_uses']==1 for r in grid),
 'other_hours_quiet':all(r['guest_arrivals']==r['ride_uses']==0 for r in grid if r['hour_of_day'] not in [9,10]),
 'runtime_database_tls':before['database_tls'][0]['ssl'] and after['database_tls'][0]['ssl'],
 'both_cloud_pollers_fresh':len(after['workers'])==2 and all(float(r['heartbeat_age_seconds'])<90 for r in after['workers']),
 'observed_delivery_under_sixty_seconds':float(a['max_delivery_lag_seconds'])<60,
}
report={'status':'VERIFIED' if all(checks.values()) else 'REVIEW_REQUIRED','verified_at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,
 'before_totals':b,'after_totals':a,'observed_max_delivery_lag_seconds':a['max_delivery_lag_seconds'],
 'guest_booking_id':'2680caeb-3b95-4214-b671-8931bd7086e2','simulation_timezone':'Asia/Colombo',
 'simulation_times':{'check_in':'2026-10-19T09:10:00+05:30','first_ride':'2026-10-19T09:20:00+05:30','second_ride':'2026-10-19T10:05:00+05:30'},
 'mock_only':True,'real_money_charged':False,'limitations':'Observed demonstration timing is not a latency SLA/load test; rides and arrivals do not prove physical attendance or occupancy.'}
(root/'docs/evidence/step10e-flow-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
assert all(checks.values()),'Inspect failed reconciliation checks'
