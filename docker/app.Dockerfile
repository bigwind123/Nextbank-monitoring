FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY monitoring ./monitoring
COPY scripts ./scripts
COPY config ./config
RUN mkdir -p /state && chown 1000:0 /state
USER 1000:0
ENTRYPOINT ["python", "-m"]
