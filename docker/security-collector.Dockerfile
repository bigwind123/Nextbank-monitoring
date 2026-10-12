FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends unixodbc unixodbc-dev freetds-dev tdsodbc gcc g++ && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt pyodbc==5.3.0
COPY monitoring ./monitoring
USER 1000:0
ENTRYPOINT ["python", "-m", "monitoring.collectors", "security-events"]
