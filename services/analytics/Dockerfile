FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/analytics/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/analytics/analytics_app ./analytics_app
COPY services/analytics/alembic ./alembic
COPY services/analytics/alembic.ini .
COPY packages/common/wonderland_events ./wonderland_events
COPY deploy/certs/rds-global-bundle.pem /app/certs/rds-global-bundle.pem
USER 10001:10001
CMD ["python", "-m", "analytics_app.worker"]
