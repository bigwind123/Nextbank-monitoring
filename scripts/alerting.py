import os
from pathlib import Path
from monitoring.config import settings, secret, session, request


def main():
    cfg = settings()
    os.environ.update({"ES_HOST": cfg["es_host"], "ES_PORT": str(cfg["es_port"]),
                       "ES_USERNAME": cfg["writer_user"], "ES_PASSWORD": secret("writer-password"),
                       "ES_USE_SSL": "True", "ES_VERIFY_CERTS": "True", "ES_CA_CERTS": cfg["ca_file"]})
    client = session()
    base = cfg["es"]
    for name in ["alerting-status", "alerting-status_status", "alerting-status_silence", "alerting-status_error", "alerting-status_past"]:
        response = client.head(base + "/" + name, timeout=10)
        if response.status_code == 404:
            request(client, "PUT", base, "/" + name, json={"mappings": {"properties": {
                "@timestamp": {"type": "date"}, "rule_name": {"type": "keyword"},
                "starttime": {"type": "date"}, "endtime": {"type": "date"}, "until": {"type": "date"}}}})
        else:
            response.raise_for_status()
    os.execvp("elastalert", ["elastalert", "--config", "/runtime/alerting.yml", "--verbose"])


if __name__ == "__main__":
    main()
