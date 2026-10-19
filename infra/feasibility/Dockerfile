FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/catalog/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY infra/feasibility/app/main.py ./main.py
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
