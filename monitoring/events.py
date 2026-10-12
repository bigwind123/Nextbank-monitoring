import hashlib
import json
from datetime import datetime, timezone


def event(kind, host, timestamp, parameters=None, event_id=None, caller=None):
    payload = {
        "schema_version": 1,
        "kind": kind,
        "host": host,
        "timestamp": timestamp,
        "parameters": parameters or {},
        "caller": caller,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    payload["id"] = event_id or hashlib.sha256(canonical.encode()).hexdigest()
    return payload


def now():
    return datetime.now(timezone.utc).isoformat()


def validate(payload):
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Unsupported event schema")
    for key in ("id", "kind", "host", "timestamp"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ValueError("Missing event attribute: " + key)
    datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))
    if not isinstance(payload.get("parameters"), dict):
        raise ValueError("Invalid event parameters")
    return payload


def producer():
    from kafka import KafkaProducer
    from .config import settings

    cfg = settings()
    options = cfg.get("kafka_security", {})
    return KafkaProducer(
        bootstrap_servers=cfg["kafka_brokers"],
        acks="all",
        retries=10,
        enable_idempotence=True,
        value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode(),
        key_serializer=lambda value: value.encode(),
        **options,
    )


def publish(payload, client=None):
    from .config import settings

    validate(payload)
    owned = client is None
    client = client or producer()
    try:
        client.send(settings()["event_topic"], key=payload["host"], value=payload).get(timeout=45)
        client.flush(timeout=45)
    finally:
        if owned:
            client.close(timeout=5)
