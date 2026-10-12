import json
import secrets
import time
from kafka import KafkaConsumer
from monitoring.config import settings, session, request
from monitoring.events import event, now, producer, publish


def main():
    cfg = settings()
    api = session("kibana")
    for attempt in range(120):
        data = request(api, "GET", cfg["kibana"], "/api/fleet/agent_status")
        if data.get("results", {}).get("online", 0) >= 1:
            break
        time.sleep(2)
    else:
        raise RuntimeError("Managed agent did not enroll")
    group = "verification-" + secrets.token_hex(4)
    consumer = KafkaConsumer(cfg["event_topic"], bootstrap_servers=cfg["kafka_brokers"], group_id=group,
                             auto_offset_reset="earliest", consumer_timeout_ms=60000, **cfg.get("kafka_security", {}))
    payload = event("CPU", "queue-check", now(), {"Param1": "0.75"})
    publish(payload)
    for record in consumer:
        if json.loads(record.value)["id"] == payload["id"]:
            consumer.close()
            return
    raise RuntimeError("Published event was not consumed")


if __name__ == "__main__":
    main()
