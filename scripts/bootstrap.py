import argparse
import json
import time
from pathlib import Path
import requests
from monitoring.config import settings, secret, request

ROOT = Path(__file__).resolve().parents[1]


def wait(client, base, path):
    for _ in range(240):
        try:
            response = client.get(base + path, timeout=(5, 20))
            if response.status_code == 200:
                return response.json()
        except requests.RequestException:
            pass
        time.sleep(2)
    raise TimeoutError("A required service did not become ready")


def client():
    c = requests.Session()
    c.verify = settings()["ca_file"]
    c.auth = ("elastic", secret("elastic-password"))
    c.headers["kbn-xsrf"] = "bootstrap"
    return c


def security():
    cfg = settings()
    c = client()
    wait(c, cfg["es"], "/_cluster/health?wait_for_status=yellow&timeout=20s")
    request(c, "POST", cfg["es"], "/_security/user/kibana_system/_password", json={"password": secret("kibana-password")})
    writer = {"cluster": ["monitor", "manage_ilm", "manage_index_templates", "manage_ingest_pipelines"], "indices": [{
        "names": ["logs-*", "metrics-*", "traces-*", "synthetics-*", "heartbeat-*", "alerting-status*"],
        "privileges": ["read", "write", "create_index", "auto_configure", "view_index_metadata", "manage"]}]}
    request(c, "PUT", cfg["es"], "/_security/role/pipeline_writer", json=writer)
    request(c, "PUT", cfg["es"], "/_security/user/" + cfg["writer_user"], json={"password": secret("writer-password"), "roles": ["pipeline_writer"]})
    # Each LDAP user has its own native identity; Kibana role privileges remain per user.
    reader = {"elasticsearch": {"cluster": ["monitor"], "indices": [{"names": ["logs-*", "metrics-*", "traces-*", "synthetics-*", "heartbeat-*"],
                "privileges": ["read", "view_index_metadata"]}]}, "kibana": [{"base": ["read"], "feature": {}, "spaces": ["*"]}]}
    # Kibana is not ready at this stage. Native role application privileges implement its base read role.
    native_reader = {**reader["elasticsearch"], "applications": [{"application": "kibana-.kibana", "privileges": ["read"], "resources": ["*"]}]}
    request(c, "PUT", cfg["es"], "/_security/role/monitoring_reader", json=native_reader)
    request(c, "PUT", cfg["es"], "/_security/user/" + cfg["reader_user"], json={"password": secret("reader-password"), "roles": ["monitoring_reader"]})
    request(c, "PUT", cfg["es"], "/_security/user/" + cfg["fleet_operator"], json={"password": secret("fleet-operator-password"), "roles": ["kibana_admin"]})
    policy = json.loads((ROOT / "config" / "ilm-hot-cold.json").read_text())
    request(c, "PUT", cfg["es"], "/_ilm/policy/hot-cold-retention", json=policy)
    for prefix in ["logs", "metrics", "traces", "synthetics"]:
        template = {"index_patterns": [prefix + "-*-*"], "priority": 1, "data_stream": {}, "template": {
            "settings": {"index.lifecycle.name": "hot-cold-retention", "index.number_of_shards": 1, "index.number_of_replicas": 0,
                         "index.routing.allocation.include._tier_preference": "data_hot"},
            "mappings": {"properties": {"@timestamp": {"type": "date"}}}}}
        request(c, "PUT", cfg["es"], "/_index_template/" + prefix + "-platform", json=template)
    print("Elasticsearch security and retention initialized")


def ensure(c, base, path, body):
    response = c.get(base + path, timeout=30)
    if response.status_code == 404:
        return request(c, "POST", base, path.rsplit("/", 1)[0], json=body)
    response.raise_for_status()
    return response.json()


def package(c, base, name):
    result = request(c, "GET", base, "/api/fleet/epm/packages/" + name)
    info = result.get("item", result.get("response", result))
    version = info["version"]
    request(c, "POST", base, "/api/fleet/epm/packages/" + name + "/" + version, json={"force": True})
    return {"name": name, "version": version}


def fleet():
    cfg = settings()
    c = client()
    wait(c, cfg["kibana"], "/api/status")
    request(c, "POST", cfg["kibana"], "/api/fleet/setup", json={})
    request(c, "PUT", cfg["kibana"], "/api/security/role/monitoring_reader", json={
        "elasticsearch": {"cluster": ["monitor"], "indices": [{"names": ["logs-*", "metrics-*", "traces-*", "synthetics-*", "heartbeat-*"], "privileges": ["read", "view_index_metadata"]}]},
        "kibana": [{"base": ["read"], "feature": {}, "spaces": ["*"]}]})
    request(c, "PUT", cfg["kibana"], "/api/security/role/fleet_operator", json={
        "elasticsearch": {"cluster": ["monitor"], "indices": []},
        "kibana": [{"base": [], "feature": {"fleet": ["all"], "fleetv2": ["all"]}, "spaces": ["*"]}]})
    request(c, "PUT", cfg["es"], "/_security/user/" + cfg["fleet_operator"], json={"password": secret("fleet-operator-password"), "roles": ["fleet_operator"]})
    fleet_pkg = package(c, cfg["kibana"], "fleet_server")
    apm_pkg = package(c, cfg["kibana"], "apm")
    for policy_id, name in [("fleet-server-policy", "Fleet server"), ("managed-apm-policy", "Managed APM")]:
        ensure(c, cfg["kibana"], "/api/fleet/agent_policies/" + policy_id, {"id": policy_id, "name": name, "namespace": "default", "monitoring_enabled": ["logs", "metrics"]})
    existing = request(c, "GET", cfg["kibana"], "/api/fleet/package_policies", params={"perPage": 100})
    names = {item["name"] for item in existing.get("items", [])}
    if "fleet-server" not in names:
        request(c, "POST", cfg["kibana"], "/api/fleet/package_policies", json={
            "name": "fleet-server", "namespace": "default", "policy_id": "fleet-server-policy", "package": fleet_pkg,
            "inputs": [{"type": "fleet-server", "enabled": True, "streams": []}]})
    if "managed-apm" not in names:
        variables = {"host": {"value": cfg["listen_host"] + ":8200", "type": "text"},
                     "secret_token": {"value": secret("apm-secret"), "type": "text"},
                     "ssl.enabled": {"value": True, "type": "bool"},
                     "ssl.certificate": {"value": "/runtime/certs/managed-apm/managed-apm.crt", "type": "text"},
                     "ssl.key": {"value": "/runtime/certs/managed-apm/managed-apm.key", "type": "text"}}
        request(c, "POST", cfg["kibana"], "/api/fleet/package_policies", json={
            "name": "managed-apm", "namespace": "default", "policy_id": "managed-apm-policy", "package": apm_pkg,
            "inputs": [{"type": "apm", "enabled": True, "streams": [], "vars": variables}]})
    # Extend default Fleet output with the local CA; URLs and credential values stay in runtime files.
    outputs = request(c, "GET", cfg["kibana"], "/api/fleet/outputs")
    for output in outputs.get("items", []):
        if output.get("is_default"):
            ca = Path(cfg["ca_file"]).read_text()
            import yaml
            request(c, "PUT", cfg["kibana"], "/api/fleet/outputs/" + output["id"], json={
                "name": output["name"], "type": "elasticsearch", "hosts": [cfg["es"]],
                "config_yaml": yaml.safe_dump({"ssl.certificate_authorities": [ca]})})
    token = request(c, "POST", cfg["es"], "/_security/service/elastic/fleet-server/credential/token")
    p = Path(cfg["secret_dir"])
    (p / "fleet-service").write_text(token["token"]["value"])
    enrollment = request(c, "POST", cfg["kibana"], "/api/fleet/enrollment_api_keys", json={"policy_id": "managed-apm-policy"})
    (p / "agent-enrollment").write_text(enrollment["item"]["api_key"])
    if Path("/runtime/vsphere.json").exists():
        vsphere(c, cfg, p)
    for file in p.iterdir():
        file.chmod(0o640)
    print("Fleet, managed APM and APM integration assets initialized")


def vsphere(c, cfg, path):
    source = json.loads(Path("/runtime/vsphere.json").read_text())
    pkg = package(c, cfg["kibana"], "vsphere")
    ensure(c, cfg["kibana"], "/api/fleet/agent_policies/vsphere-policy", {"id": "vsphere-policy", "name": "Virtual infrastructure", "namespace": "default", "monitoring_enabled": ["logs", "metrics"]})
    meta = request(c, "GET", cfg["kibana"], "/api/fleet/epm/packages/vsphere/" + pkg["version"])
    streams = []
    item = meta.get("item", {})
    for stream in item.get("data_streams", []):
        dataset = stream.get("dataset") or "vsphere." + stream["path"]
        streams.append({"enabled": True, "data_stream": {"type": "metrics", "dataset": dataset}, "vars": {
            "hosts": {"value": source["hosts"], "type": "text"}, "username": {"value": source["user"], "type": "text"},
            "password": {"value": secret("vsphere-password"), "type": "password"},
            "ssl.verification_mode": {"value": "full", "type": "text"}}})
    request(c, "POST", cfg["kibana"], "/api/fleet/package_policies", json={"name": "vsphere", "namespace": "default", "policy_id": "vsphere-policy", "package": pkg,
        "inputs": [{"type": "vsphere/metrics", "enabled": True, "streams": streams}]})
    enrollment = request(c, "POST", cfg["kibana"], "/api/fleet/enrollment_api_keys", json={"policy_id": "vsphere-policy"})
    (path / "vsphere-enrollment").write_text(enrollment["item"]["api_key"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["security", "fleet"])
    args = parser.parse_args()
    globals()[args.stage]()


if __name__ == "__main__":
    main()
