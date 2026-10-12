import argparse
import base64
import hashlib
import ipaddress
import json
import os
import secrets
import shutil
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlunsplit, urlsplit
import yaml

ROOT = Path(__file__).resolve().parents[1]


def default_runtime():
    base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "ObservabilityPlatform"


def address(scheme, host, port):
    return urlunsplit((scheme, host + ":" + str(port), "", "", ""))


def write(path, data, sensitive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8", newline="\n")
    if os.name != "nt":
        path.chmod(0o600 if sensitive else 0o644)


def ss_hash(value):
    salt = secrets.token_bytes(16)
    return "{SSHA}" + base64.b64encode(hashlib.sha1(value.encode() + salt).digest() + salt).decode()


def init(runtime, operator=None):
    if runtime == ROOT or ROOT in runtime.parents:
        raise ValueError("Runtime configuration must be stored outside the repository")
    runtime.mkdir(parents=True, exist_ok=True)
    input_cfg = json.loads(operator.read_text(encoding="utf-8")) if operator else {}
    for folder in ("secrets", "certs", "monitors", "rules"):
        (runtime / folder).mkdir(exist_ok=True)
    values = {}
    secret_names = ["elastic-password", "kibana-password", "writer-password", "fleet-operator-password",
                    "reader-password", "ldap-bind-password", "apm-secret", "security-encryption", "saved-objects-encryption", "reporting-encryption"]
    for name in secret_names:
        p = runtime / "secrets" / name
        if not p.exists():
            write(p, secrets.token_urlsafe(36), True)
        values[name] = p.read_text(encoding="utf-8").strip()
    for name, value in input_cfg.get("secrets", {}).items():
        if not isinstance(value, str) or not value:
            raise ValueError("Empty external secret")
        if Path(name).name != name:
            raise ValueError("Invalid secret name")
        write(runtime / "secrets" / name, value, True)
    listen = str(ipaddress.IPv4Address(0))
    local_bind = socket.gethostbyname("localhost")
    cfg = {
        "secret_dir": "/runtime/secrets", "ca_file": "/runtime/certs/ca/ca.crt", "state_dir": "/state",
        "listen_host": listen, "es": address("https", "coordination", 9200), "es_host": "coordination", "es_port": 9200,
        "kibana": address("https", "kibana", 5601), "fleet": address("https", "fleet", 8220),
        "writer_user": "pipeline_writer", "fleet_operator": "fleet_operator", "reader_user": "monitoring_reader",
        "kafka_brokers": ["kafka-" + str(i) + ":9092" for i in (1, 2, 3)],
        "event_topic": "alert-events", "dead_topic": "alert-dead-letter",
        "ldap": {"base": address("ldaps", "directory", 636), "base_dn": "dc=monitoring,dc=invalid",
                 "bind_dn": "cn=manager,dc=monitoring,dc=invalid", "filter": "(uid={user})", "ca_file": "/runtime/certs/ca/ca.crt"},
        "itsm": {"base": None, "user": None, "caller": None}, "collectors": {},
        "agent_check_seconds": 60,
    }
    for key in ("itsm", "ldap", "collectors", "kafka_security"):
        if key in input_cfg:
            if key in ("ldap", "itsm"):
                cfg[key].update(input_cfg[key])
            else:
                cfg[key] = input_cfg[key]
    # The writer-facing service addresses are generated locally or supplied externally.
    for key in ("es", "es_host", "es_port", "kibana", "fleet", "kafka_brokers", "writer_user", "fleet_operator", "reader_user", "ca_file"):
        if key in input_cfg:
            cfg[key] = input_cfg[key]
    write(runtime / "platform.json", json.dumps(cfg, ensure_ascii=False, indent=2), True)
    write(runtime / "es-base", cfg["es"])
    write(runtime / "fleet-base", cfg["fleet"])
    kafka_id = runtime / "kafka-id"
    if not kafka_id.exists():
        write(kafka_id, base64.urlsafe_b64encode(secrets.token_bytes(16)).decode().rstrip("="))
    brokers = ",".join(cfg["kafka_brokers"])
    compose = {
        "RUNTIME_DIR": runtime.as_posix(), "LISTEN_HOST": listen, "LOCAL_BIND": local_bind,
        "ES_PORT": "9200", "WEB_PORT": "8443", "FLEET_PORT": "8220", "APM_PORT": "8200",
        "MANAGED_APM_PORT": "8201", "NETWORK_PORT": "5400",
        "KAFKA_CLUSTER_ID": kafka_id.read_text().strip(), "KAFKA_BROKERS": brokers,
        "KAFKA_QUORUM": ",".join(str(i) + "@kafka-" + str(i) + ":9093" for i in (1, 2, 3)),
        "KAFKA_LISTENERS": "INTERNAL://:" + str(9092) + ",CONTROLLER://:" + str(9093),
        "LDAP_LISTEN": "ldaps:///",
        **{"KAFKA_ADVERTISE_" + str(i): "INTERNAL://kafka-" + str(i) + ":9092" for i in (1, 2, 3)},
    }
    write(runtime / "compose.env", "\n".join(k + "='" + str(v).replace("'", "") + "'" for k, v in compose.items()) + "\n", True)
    elastic = {
        "LISTEN_HOST": listen, "ES_BASE": cfg["es"], "FLEET_BASE": cfg["fleet"],
        "KIBANA_USER": "kibana_system", "KIBANA_PASSWORD": values["kibana-password"],
        "KIBANA_BASE": cfg["kibana"], "FLEET_OPERATOR": cfg["fleet_operator"], "FLEET_OPERATOR_PASSWORD": values["fleet-operator-password"],
        "WRITER_USER": cfg["writer_user"], "WRITER_PASSWORD": values["writer-password"],
        "APM_LISTEN": listen + ":8200", "APM_SECRET": values["apm-secret"],
        "KAFKA_BROKERS": brokers, "KAFKA_BROKERS_JSON": json.dumps(cfg["kafka_brokers"]),
        "SECURITY_ENCRYPTION_KEY": values["security-encryption"], "SAVED_OBJECTS_ENCRYPTION_KEY": values["saved-objects-encryption"],
        "REPORTING_ENCRYPTION_KEY": values["reporting-encryption"],
    }
    write(runtime / "elastic.env", "\n".join(k + "='" + str(v).replace("'", "") + "'" for k, v in elastic.items()) + "\n", True)
    instances = []
    for name in ("master", "hot", "cold", "coordination", "kibana", "nginx", "ldap", "fleet", "apm", "managed-apm"):
        dns = [name, "localhost"]
        if name == "ldap":
            dns.append("directory")
        instances.append({"name": name, "dns": dns, "ip": [local_bind]})
    write(runtime / "instances.yml", yaml.safe_dump({"instances": instances}))
    nginx = (ROOT / "config" / "nginx.conf.template").read_text(encoding="utf-8")
    nginx = nginx.replace("${KIBANA_BASE}", cfg["kibana"]).replace("${LDAP_AUTH_BASE}", address("http", "ldap-auth", 8888))
    write(runtime / "nginx.conf", nginx)
    roles = {"master": ["master", "ingest", "transform", "remote_cluster_client"],
             "hot": ["data_hot", "data_content"], "cold": ["data_cold"], "coordination": []}
    for node, node_roles in roles.items():
        es = yaml.safe_load((ROOT / "config" / "elasticsearch.yml").read_text())
        es["node.roles"] = node_roles
        es["node.name"] = node
        for key in list(es):
            if isinstance(es[key], str):
                es[key] = es[key].replace("${NODE_NAME}", node)
        write(runtime / (node + ".yml"), yaml.safe_dump(es))
    root_dn = "cn=manager,dc=monitoring,dc=invalid"
    ldap_conf = "\n".join([
        "include /etc/ldap/schema/core.schema", "include /etc/ldap/schema/cosine.schema", "include /etc/ldap/schema/inetorgperson.schema",
        "pidfile /tmp/slapd.pid", "argsfile /tmp/slapd.args", "modulepath /usr/lib/ldap", "moduleload back_mdb",
        "TLSCertificateFile /runtime/certs/ldap/ldap.crt", "TLSCertificateKeyFile /runtime/certs/ldap/ldap.key",
        "TLSCACertificateFile /runtime/certs/ca/ca.crt", "database mdb", "maxsize 1073741824",
        "suffix dc=monitoring,dc=invalid", "rootdn " + root_dn, "rootpw " + ss_hash(values["ldap-bind-password"]),
        "directory /var/lib/ldap", "access to attrs=userPassword by self write by anonymous auth by * none",
        "access to * by dn.exact=\"" + root_dn + "\" read by self read by * none",
    ])
    write(runtime / "ldap.conf", ldap_conf + "\n", True)
    ldif = "\n".join(["dn: dc=monitoring,dc=invalid", "objectClass: top", "objectClass: dcObject", "objectClass: organization",
                      "o: Monitoring", "dc: monitoring", "", "dn: uid=monitoring_reader,dc=monitoring,dc=invalid",
                      "objectClass: inetOrgPerson", "cn: Monitoring Reader", "sn: Reader", "uid: monitoring_reader",
                      "userPassword: " + ss_hash(values["reader-password"]), ""])
    write(runtime / "directory.ldif", ldif, True)
    monitors = input_cfg.get("monitors") or [{"type": "http", "id": "kibana-health", "name": "Kibana health", "schedule": "@every 5s",
                 "urls": [cfg["kibana"] + "/api/status"], "check.response.status": [200],
                 "ssl.certificate_authorities": [cfg["ca_file"]]}]
    write(runtime / "monitors" / "targets.yml", yaml.safe_dump(monitors))
    render_rules(runtime, input_cfg)
    profiles = []
    if cfg["itsm"].get("base"):
        for key in ("user", "caller"):
            if not cfg["itsm"].get(key):
                raise ValueError("Event center configuration is missing " + key)
        if not (runtime / "secrets" / "itsm-password").exists():
            raise ValueError("Event center password must be supplied externally")
        profiles.append("itsm")
    profiles.extend(cfg["collectors"].keys())
    if input_cfg.get("vsphere"):
        profiles.append("vsphere")
        write(runtime / "vsphere.json", json.dumps(input_cfg["vsphere"]), True)
    write(runtime / "profiles.json", json.dumps(profiles))
    write(runtime / "host.json", json.dumps({"web": address("https", "localhost", 8443), "es": address("https", "localhost", 9200),
                                            "fleet": address("https", "localhost", 8220), "apm": address("https", "localhost", 8200)}), True)
    return cfg


def render_rules(runtime, operator):
    catalog = json.loads((ROOT / "config" / "rule-catalog.json").read_text(encoding="utf-8"))
    selection = operator.get("rules", {})
    for path in (runtime / "rules").glob("*.yaml"):
        path.unlink()
    active = 0
    for item in catalog:
        rule = item["rule"]
        override = selection.get(item["id"], {})
        enabled = override.get("enabled", item["default_enabled"])
        if not enabled:
            continue
        parameters = override.get("parameters", {})
        for key in item["inputs"]:
            if key not in parameters:
                raise ValueError("Rule " + item["id"] + " requires external parameter " + key)
        def substitute(value):
            if isinstance(value, dict):
                return {key: substitute(child) for key, child in value.items()}
            if isinstance(value, list):
                return [substitute(child) for child in value]
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                return parameters[value[2:-1]]
            return value
        rule = substitute(rule)
        rule.update(override.get("config", {}))
        rule["is_enabled"] = True
        write(runtime / "rules" / (item["id"] + ".yaml"), yaml.safe_dump(rule, allow_unicode=True))
        active += 1
    if not active:
        raise ValueError("At least one monitoring rule must be enabled")
    alerting = {"rules_folder": "/runtime/rules", "run_every": {"seconds": 10}, "buffer_time": {"minutes": 15},
                "es_host": "${ES_HOST}", "es_port": "${ES_PORT}", "use_ssl": True, "verify_certs": True,
                "ca_certs": "/runtime/certs/ca/ca.crt", "es_username": "${ES_USERNAME}", "es_password": "${ES_PASSWORD}",
                "writeback_index": "alerting-status", "alert_time_limit": {"days": 2}}
    write(runtime / "alerting.yml", yaml.safe_dump(alerting))


def compose(runtime, arguments):
    engine = shutil.which("docker")
    if not engine:
        raise SystemExit("Docker Engine with Compose is required")
    if not (runtime / "compose.env").exists():
        raise SystemExit("Run init first")
    profiles = json.loads((runtime / "profiles.json").read_text())
    command = [engine, "compose", "--project-directory", str(ROOT), "--env-file", str(runtime / "compose.env"), "-f", str(ROOT / "compose.yaml")]
    for profile in profiles:
        command.extend(["--profile", profile])
    result = subprocess.run(command + arguments, cwd=ROOT)
    if result.returncode:
        raise SystemExit(result.returncode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["init", "up", "down", "status", "config", "check", "login", "ocp"])
    parser.add_argument("--runtime", type=Path, default=default_runtime())
    parser.add_argument("--operator", type=Path)
    parser.add_argument("--namespace", default="observability")
    parser.add_argument("--storage-class")
    parser.add_argument("--image-prefix")
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    if args.action == "init":
        init(runtime, args.operator)
        print("Runtime initialized outside the repository")
    elif args.action == "up":
        compose(runtime, ["up", "-d", "--build"])
    elif args.action == "down":
        compose(runtime, ["down"])
    elif args.action == "status":
        compose(runtime, ["ps", "--all"])
    elif args.action == "config":
        compose(runtime, ["config", "--quiet"])
    elif args.action == "check":
        from .smoke import main as smoke
        smoke(runtime)
    elif args.action == "login":
        print("Local Kibana:", json.loads((runtime / "host.json").read_text())["web"])
        print("Local directory user: monitoring_reader")
        print("Password file:", runtime / "secrets" / "reader-password")
    else:
        if not all([args.storage_class, args.image_prefix, args.operator]):
            raise SystemExit("OCP requires external operator settings, storage class and image prefix")
        from .ocp import render
        render(runtime, args.namespace, args.storage_class, args.image_prefix)


if __name__ == "__main__":
    main()
