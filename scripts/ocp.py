import json
from pathlib import Path
import yaml
from .platform import ROOT, write


def render(runtime, namespace, storage_class, image_prefix):
    cfg = json.loads((runtime / "platform.json").read_text())
    if cfg["es_host"] == "coordination" or any(host.startswith("kafka-") for host in cfg["kafka_brokers"]):
        raise ValueError("Provide the independent Elasticsearch and Kafka service addresses externally")
    required = ["fleet-service", "agent-enrollment"]
    if any(not (runtime / "secrets" / name).exists() for name in required):
        raise ValueError("Initialize Fleet on the Linux deployment before rendering OCP")
    output = runtime / "ocp"
    output.mkdir(exist_ok=True)
    docs = [{"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": namespace}}]
    def resource(kind, name, spec=None, version="v1", **kwargs):
        item = {"apiVersion": version, "kind": kind, "metadata": {"name": name, "namespace": namespace}, **kwargs}
        if spec is not None:
            item["spec"] = spec
        return item
    private = {}
    for path in runtime.rglob("*"):
        if not path.is_file() or output in path.parents or path.name in {"ca.key", "compose.env", "host.json"}:
            continue
        relative = path.relative_to(runtime).as_posix()
        if any(part.startswith(".") for part in path.relative_to(runtime).parts):
            continue
        if path.suffix not in {".json", ".env", ".yaml", ".yml", ".conf", ".crt", ".key"} and path.parent.name != "secrets" and path.name not in {"es-base", "fleet-base"}:
            continue
        private[relative.replace("/", "__")] = path.read_text(encoding="utf-8")
    public_configs = {path.name: path.read_text(encoding="utf-8") for path in (ROOT / "config").iterdir() if path.is_file() and path.name != "rule-catalog.json"}
    scripts = {path.name: path.read_text(encoding="utf-8") for path in (ROOT / "scripts").glob("*.sh")}
    docs.extend([
        resource("Secret", "platform-private", type="Opaque", stringData=private),
        resource("ConfigMap", "platform-config", data=public_configs),
        resource("ConfigMap", "platform-scripts", data=scripts),
        resource("PersistentVolumeClaim", "platform-runtime", {"accessModes": ["ReadWriteMany"], "storageClassName": storage_class,
                 "resources": {"requests": {"storage": "1Gi"}}}),
    ])
    for name in ("default-service", "fleet-agent", "heartbeat-service"):
        docs.append(resource("ServiceAccount", name))
    init_command = (
        "from pathlib import Path; import shutil,os; root=Path('/runtime'); "
        "[(lambda src: (lambda dst: (dst.parent.mkdir(parents=True,exist_ok=True),shutil.copyfile(src,dst),dst.chmod(0o640)))(root/src.name.replace('__','/')))(p) "
        "for p in Path('/input').iterdir() if p.is_file() and not p.name.startswith('.')]; root.chmod(0o770)"
    )
    docs.append(resource("Job", "prepare-runtime", {"backoffLimit": 2, "template": {"spec": {
        "serviceAccountName": "default-service", "restartPolicy": "OnFailure", "containers": [{
            "name": "prepare", "image": image_prefix.rstrip("/") + "/app:local", "command": ["python", "-c", init_command],
            "volumeMounts": [{"name": "input", "mountPath": "/input", "readOnly": True}, {"name": "runtime", "mountPath": "/runtime"}]}],
        "volumes": [{"name": "input", "secret": {"secretName": "platform-private", "defaultMode": 288}},
                    {"name": "runtime", "persistentVolumeClaim": {"claimName": "platform-runtime"}}]}}}, version="batch/v1"))
    services = yaml.safe_load((ROOT / "compose.yaml").read_text())["services"]
    selected = ["kibana", "ldap-auth", "nginx", "fleet", "managed-apm", "apm", "logstash-apm", "logstash-network", "heartbeat", "alerting", "fleet-monitor"]
    profiles = json.loads((runtime / "profiles.json").read_text())
    for name in ["event-worker", "f5-collector", "security-agent-collector", "security-event-collector", "vsphere-agent"]:
        if any(profile in profiles for profile in services[name].get("profiles", [])):
            selected.append(name)
    elastic_env = {}
    for line in (runtime / "elastic.env").read_text().splitlines():
        key, value = line.split("=", 1)
        elastic_env[key] = value.strip("'")
    docs.append(resource("Secret", "elastic-environment", type="Opaque", stringData=elastic_env))
    ready = ["python", "-c", "from pathlib import Path; import time; p=Path('/runtime/platform.json');\nwhile not p.exists(): time.sleep(2)"]
    for name in selected:
        source = services[name]
        image = source.get("image")
        if image.startswith("observability-"):
            suffix = "alerting" if name == "alerting" else "security-collector" if name == "security-event-collector" else "app"
            image = image_prefix.rstrip("/") + "/" + suffix + ":local"
        container = {"name": name, "image": image, "env": [{"name": "PLATFORM_CONFIG", "value": "/runtime/platform.json"}],
                     "resources": {"requests": {"cpu": "100m", "memory": "256Mi"}, "limits": {"memory": "2Gi"}},
                     "volumeMounts": [{"name": "runtime", "mountPath": "/runtime"}, {"name": "scripts", "mountPath": "/scripts", "readOnly": True}]}
        if "entrypoint" in source:
            container["command"] = source["entrypoint"]
        elif image.endswith("/app:local"):
            container["command"] = ["python", "-m"]
        if "command" in source:
            container["args"] = source["command"]
        if source.get("env_file"):
            container["envFrom"] = [{"secretRef": {"name": "elastic-environment"}}]
        for key, value in source.get("environment", {}).items():
            container["env"].append({"name": key, "value": str(value)})
        volume_spec = [{"name": "runtime", "persistentVolumeClaim": {"claimName": "platform-runtime"}},
                       {"name": "scripts", "configMap": {"name": "platform-scripts"}},
                       {"name": "configs", "configMap": {"name": "platform-config"}}]
        for volume in source.get("volumes", []):
            pieces = volume.split(":")
            if pieces[0].startswith("./config/"):
                container["volumeMounts"].append({"name": "configs", "mountPath": pieces[1], "subPath": Path(pieces[0]).name, "readOnly": True})
            elif pieces[0].endswith("/nginx.conf"):
                container["volumeMounts"].append({"name": "runtime", "mountPath": "/etc/nginx/nginx.conf", "subPath": "nginx.conf", "readOnly": True})
            elif pieces[0].endswith("-data"):
                claim = name + "-state"
                docs.append(resource("PersistentVolumeClaim", claim, {"accessModes": ["ReadWriteOnce"], "storageClassName": storage_class,
                    "resources": {"requests": {"storage": "2Gi"}}}))
                volume_spec.append({"name": "state", "persistentVolumeClaim": {"claimName": claim}})
                container["volumeMounts"].append({"name": "state", "mountPath": pieces[1]})
        sa = "fleet-agent" if name in {"fleet", "managed-apm", "vsphere-agent"} else "heartbeat-service" if name == "heartbeat" else "default-service"
        if sa == "fleet-agent":
            container["securityContext"] = {"runAsUser": 0}
        elif sa == "heartbeat-service":
            container["securityContext"] = {"capabilities": {"drop": ["ALL"], "add": ["NET_RAW"]}, "allowPrivilegeEscalation": False}
        pod = {"serviceAccountName": sa, "containers": [container], "volumes": volume_spec,
               "initContainers": [{"name": "runtime-ready", "image": image_prefix.rstrip("/") + "/app:local", "command": ready,
                                   "volumeMounts": [{"name": "runtime", "mountPath": "/runtime"}]}]}
        if name not in {"fleet", "managed-apm", "vsphere-agent"}:
            pod["securityContext"] = {"runAsNonRoot": True}
        docs.append(resource("Deployment", name, {"replicas": 1, "selector": {"matchLabels": {"app": name}},
            "strategy": {"type": "Recreate"}, "template": {"metadata": {"labels": {"app": name}}, "spec": pod}}, version="apps/v1"))
        ports = {"kibana": (5601, "TCP"), "ldap-auth": (8888, "TCP"), "nginx": (8443, "TCP"), "fleet": (8220, "TCP"),
                 "managed-apm": (8200, "TCP"), "apm": (8200, "TCP"), "logstash-network": (5400, "UDP")}
        if name in ports:
            port, protocol = ports[name]
            docs.append(resource("Service", name, {"selector": {"app": name}, "ports": [{"name": "service", "port": port, "targetPort": port, "protocol": protocol}]}))
    for name, port in [("nginx", 8443), ("fleet", 8220), ("apm", 8200), ("managed-apm", 8200)]:
        docs.append(resource("Route", name, {"to": {"kind": "Service", "name": name}, "port": {"targetPort": "service"},
            "tls": {"termination": "passthrough", "insecureEdgeTerminationPolicy": "None"}}, version="route.openshift.io/v1"))
    write(output / "services.yaml", yaml.safe_dump_all(docs, sort_keys=False), sensitive=True)
    print("OCP resources rendered outside the repository; prepare-runtime requires a RWX storage class")
