FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/catalog/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY services/catalog/app /app/services/catalog/app
COPY services/catalog/alembic /app/services/catalog/alembic
COPY services/catalog/alembic.ini /app/services/catalog/alembic.ini
COPY services/booking/booking_app /app/services/booking/booking_app
COPY services/booking/alembic /app/services/booking/alembic
COPY services/booking/alembic.ini /app/services/booking/alembic.ini
COPY services/payment/payment_app /app/services/payment/payment_app
COPY services/payment/alembic /app/services/payment/alembic
COPY services/payment/alembic.ini /app/services/payment/alembic.ini
COPY services/admission/admission_app /app/services/admission/admission_app
COPY services/admission/alembic /app/services/admission/alembic
COPY services/admission/alembic.ini /app/services/admission/alembic.ini
COPY services/analytics/analytics_app /app/services/analytics/analytics_app
COPY services/analytics/alembic /app/services/analytics/alembic
COPY services/analytics/alembic.ini /app/services/analytics/alembic.ini
COPY packages/common/wonderland_events /app/wonderland_events
COPY deploy/database_bootstrap/db_bootstrap /app/db_bootstrap
COPY deploy/certs/rds-global-bundle.pem /app/certs/rds-global-bundle.pem
ENV PYTHONPATH=/app:/app/services/catalog:/app/services/booking:/app/services/payment:/app/services/admission:/app/services/analytics
USER 10001:10001
CMD ["python", "-m", "db_bootstrap.bootstrap"]
