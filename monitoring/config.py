import json
import os
from pathlib import Path


def settings():
    return json.loads(Path(os.environ["PLATFORM_CONFIG"]).read_text(encoding="utf-8"))


def secret(name):
    return Path(settings()["secret_dir"], name).read_text(encoding="utf-8").strip()


def session(service="es"):
    import requests

    cfg = settings()
    result = requests.Session()
    result.verify = cfg["ca_file"]
    if service == "es":
        result.auth = (cfg["writer_user"], secret("writer-password"))
    elif service == "kibana":
        result.auth = (cfg["fleet_operator"], secret("fleet-operator-password"))
        result.headers["kbn-xsrf"] = "platform"
    return result


def request(client, method, base, path, **kwargs):
    response = client.request(method, base.rstrip("/") + path, timeout=(5, 45), **kwargs)
    response.raise_for_status()
    return response.json() if response.content else {}
