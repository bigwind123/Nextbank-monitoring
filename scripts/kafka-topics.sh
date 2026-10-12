set -euo pipefail
for attempt in $(seq 1 120); do
    if /opt/kafka/bin/kafka-topics.sh --bootstrap-server "$KAFKA_BROKERS" --list >/dev/null 2>&1; then break; fi
    sleep 2
done
for topic in apm-transaction apm-span apm-error apm-metric apm-default alert-events alert-dead-letter; do
    /opt/kafka/bin/kafka-topics.sh --bootstrap-server "$KAFKA_BROKERS" --create --if-not-exists --topic "$topic" --partitions 3 --replication-factor 3 --config min.insync.replicas=2
done
