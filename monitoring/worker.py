import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from .config import secret, settings
from .events import validate
from .strategies import AlertHandler

LOG = logging.getLogger("event-worker")


class DeliveryStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS delivered (id TEXT PRIMARY KEY, sent_at TEXT NOT NULL)")
        self.db.commit()

    def contains(self, event_id):
        return self.db.execute("SELECT 1 FROM delivered WHERE id = ?", (event_id,)).fetchone() is not None

    def mark(self, event_id):
        self.db.execute("INSERT OR IGNORE INTO delivered VALUES (?, ?)", (event_id, datetime.now(timezone.utc).isoformat()))
        self.db.commit()


def ticket(payload, caller, operation="core/create"):
    params = {
        "ITSMCaller": payload.get("caller") or caller,
        "AlertType": payload["kind"],
        "Host": payload["host"],
        "TimeStamp": payload["timestamp"],
        **payload["parameters"],
    }
    for i in range(1, 6):
        params.setdefault("Param" + str(i), "")
    result = json.loads(AlertHandler({}).handle_alert(params))
    result["operation"] = operation
    return result


def deliver(payload, store, send, caller, operation="core/create"):
    validate(payload)
    if store.contains(payload["id"]):
        return False
    send(ticket(payload, caller, operation), payload["id"])
    store.mark(payload["id"])
    return True


def main():
    from kafka import KafkaConsumer
    from kafka.errors import KafkaError

    logging.basicConfig(level=logging.INFO)
    cfg = settings()
    if not cfg["itsm"].get("base"):
        raise SystemExit("Configure the event center before starting the event worker")
    state = Path(cfg["state_dir"])
    state.mkdir(parents=True, exist_ok=True)
    store = DeliveryStore(state / "delivery.db")
    consumer = KafkaConsumer(
        cfg["event_topic"], bootstrap_servers=cfg["kafka_brokers"], group_id="event-center-delivery",
        enable_auto_commit=False, auto_offset_reset="earliest", max_poll_records=1,
        max_poll_interval_ms=300000, **cfg.get("kafka_security", {}),
    )
    from .events import producer
    dead = producer()
    client = requests.Session()
    client.verify = cfg["itsm"].get("ca_file") or True

    def send(body, event_id):
        data = {"auth_user": cfg["itsm"]["user"], "auth_pwd": secret("itsm-password"),
                "json_data": json.dumps(body, ensure_ascii=False), "version": "1.0"}
        response = client.post(cfg["itsm"]["base"], data=data,
                               headers={"Idempotency-Key": event_id}, timeout=(5, 30))
        response.raise_for_status()
        result = response.json()
        if result.get("code", 0) != 0:
            raise ValueError("Event center rejected the incident")

    try:
        for record in consumer:
            try:
                payload = json.loads(record.value)
                validate(payload)
                ticket(payload, cfg["itsm"]["caller"])
            except (ValueError, KeyError, TypeError) as exc:
                dead.send(cfg["dead_topic"], key=str(record.partition), value={
                    "reason": type(exc).__name__, "payload_hex": record.value.hex(),
                    "partition": record.partition, "offset": record.offset,
                }).get(timeout=30)
                consumer.commit()
                LOG.warning("Invalid event moved to the dead letter topic")
                continue
            # An uncertain delivery remains uncommitted. Restart replays it with the same key.
            for attempt in range(5):
                try:
                    deliver(payload, store, send, cfg["itsm"]["caller"], cfg["itsm"].get("operation", "core/create"))
                    consumer.commit()
                    LOG.info("Event processed")
                    break
                except (requests.RequestException, ValueError):
                    if attempt == 4:
                        raise
                    time.sleep(min(2 ** attempt, 15))
    finally:
        consumer.close()
        dead.close(timeout=5)
        client.close()


if __name__ == "__main__":
    main()
