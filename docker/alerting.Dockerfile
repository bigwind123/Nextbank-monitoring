FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt requirements-alerting.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-alerting.txt
COPY monitoring ./monitoring
COPY scripts ./scripts
COPY config ./config
USER 1000:0
ENTRYPOINT ["python", "-m", "scripts.alerting"]
