FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/analytics/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY services/analytics/analytics_app /app/services/analytics/analytics_app
COPY services/analytics/alembic /app/services/analytics/alembic
COPY services/analytics/alembic.ini /app/services/analytics/alembic.ini
COPY packages/common/wonderland_events /app/wonderland_events
COPY deploy/database_bootstrap/db_bootstrap /app/db_bootstrap
COPY deploy/bi_bootstrap/bi_bootstrap /app/bi_bootstrap
COPY deploy/certs/rds-global-bundle.pem /app/certs/rds-global-bundle.pem
ENV PYTHONPATH=/app:/app/services/analytics
USER 10001:10001
CMD ["python", "-m", "bi_bootstrap.bootstrap"]
