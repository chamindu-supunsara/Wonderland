FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/catalog/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/catalog/app ./app
COPY services/catalog/alembic ./alembic
COPY services/catalog/alembic.ini .
COPY packages/common/wonderland_events ./wonderland_events
COPY deploy/certs/rds-global-bundle.pem /app/certs/rds-global-bundle.pem
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

