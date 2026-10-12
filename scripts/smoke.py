import json
import secrets
import subprocess
import time
from pathlib import Path
import requests
from .platform import ROOT


def eventually(check, label, seconds=480):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                print(label + ": passed")
                return result
        except (requests.RequestException, ValueError, KeyError, AssertionError):
            pass
        time.sleep(5)
    raise TimeoutError(label + " did not pass")


def main(runtime):
    host = json.loads((runtime / "host.json").read_text())
    ca = str(runtime / "certs" / "ca" / "ca.crt")
    client = requests.Session()
    client.verify = ca
    client.auth = ("elastic", (runtime / "secrets" / "elastic-password").read_text().strip())
    def get(path):
        response = client.get(host["es"] + path, timeout=(5, 20))
        response.raise_for_status()
        return response.json()
    eventually(lambda: get("/_cluster/health").get("number_of_nodes") == 4, "Elasticsearch nodes")
    nodes = get("/_nodes?filter_path=nodes.*.roles")["nodes"].values()
    assert sum(not n["roles"] for n in nodes) == 1
    assert any("data_hot" in n["roles"] for n in nodes)
    assert any("data_cold" in n["roles"] for n in nodes)
    print("Node roles: passed")
    eventually(lambda: client.get(host["web"] + "/api/status", timeout=20).status_code == 401, "LDAP access gate")
    reader = requests.Session()
    reader.verify = ca
    reader.auth = ("monitoring_reader", (runtime / "secrets" / "reader-password").read_text().strip())
    eventually(lambda: reader.get(host["web"] + "/api/status", timeout=30).status_code == 200, "LDAP login and Kibana access")
    response = reader.delete(host["web"] + "/api/saved_objects/dashboard/" + secrets.token_hex(8),
                             headers={"kbn-xsrf": "permission-check"}, timeout=30)
    assert response.status_code == 403, "Reader role must reject a write request"
    print("Kibana authorization: passed")
    eventually(lambda: get("/heartbeat-*/_count").get("count", 0) > 0, "Heartbeat indexing")
    eventually(lambda: get("/_ilm/policy/hot-cold-retention").get("hot-cold-retention"), "ILM policy")
    # Deliver an intake transaction through the actual APM -> Kafka -> Logstash path.
    service = "stack-check-" + secrets.token_hex(4)
    intake = [
        {"metadata": {"service": {"name": service, "agent": {"name": "python", "version": "1.0.0"}}}},
        {"transaction": {"id": secrets.token_hex(8), "trace_id": secrets.token_hex(16), "name": "pipeline-check",
                         "type": "request", "duration": 1.0, "sampled": True, "span_count": {"started": 0},
                         "timestamp": int(time.time() * 1000000)}},
    ]
    body = "\n".join(json.dumps(item) for item in intake) + "\n"
    secret = (runtime / "secrets" / "apm-secret").read_text().strip()
    def send():
        result = requests.post(host["apm"] + "/intake/v2/events", data=body,
                               headers={"Content-Type": "application/x-ndjson", "Authorization": "Bearer " + secret},
                               verify=ca, timeout=30)
        return result.status_code == 202
    eventually(send, "APM intake")
    def search_transaction():
        response = client.post(host["es"] + "/traces-apm*/_search", json={"query": {"term": {"service.name": service}}, "size": 0}, timeout=30)
        response.raise_for_status()
        return response.json()["hits"]["total"]["value"] > 0
    eventually(search_transaction, "APM Kafka Logstash indexing")
    # Verify managed enrollment and queue acknowledgement inside the isolated network.
    command = ["docker", "compose", "--project-directory", str(ROOT), "--env-file", str(runtime / "compose.env"),
               "-f", str(ROOT / "compose.yaml"), "exec", "-T", "fleet-monitor", "python", "-m", "scripts.queue_check"]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Fleet or queue verification failed")
    print("Fleet enrollment and event queue: passed")


if __name__ == "__main__":
    from .platform import default_runtime
    main(default_runtime())
