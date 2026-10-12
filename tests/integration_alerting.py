import json
import secrets
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
from scripts.platform import ROOT, default_runtime, address, write, compose
from scripts.smoke import eventually


def main():
    runtime = default_runtime()
    cfg = json.loads((runtime / "platform.json").read_text())
    cfg["itsm"] = {"base": address("http", "event-center-test", 8089), "user": secrets.token_hex(8), "caller": secrets.token_hex(4)}
    write(runtime / "platform.json", json.dumps(cfg), sensitive=True)
    write(runtime / "secrets" / "itsm-password", secrets.token_urlsafe(24), sensitive=True)
    # The receiver and worker use the same isolated runtime volume, with no external accounts.
    subprocess.run(["docker", "run", "-d", "--name", "event-center-test", "--network", "observability_default", "--user", "0",
                    "--volume", str(ROOT / "tests" / "event_center_receiver.py") + ":/receiver.py:ro",
                    "--volume", str(runtime) + ":/runtime", "--entrypoint", "python", "observability-app:local", "/receiver.py"],
                   capture_output=True, check=True)
    try:
        # The runtime file must be readable by the service uid after the host writes a new secret.
        subprocess.run(["docker", "exec", "event-center-test", "chmod", "640", "/runtime/secrets/itsm-password"], check=True)
        subprocess.run(["docker", "exec", "event-center-test", "chgrp", "0", "/runtime/secrets/itsm-password"], check=True)
        write(runtime / "profiles.json", json.dumps(["itsm"]))
        compose(runtime, ["up", "-d", "event-worker"])
        host = json.loads((runtime / "host.json").read_text())
        client = requests.Session()
        client.verify = str(runtime / "certs" / "ca" / "ca.crt")
        client.auth = ("elastic", (runtime / "secrets" / "elastic-password").read_text().strip())
        hostname = "alert-check-" + secrets.token_hex(8)
        lines = []
        for i in range(9):
            timestamp = datetime.now(timezone.utc) - timedelta(seconds=12-i)
            doc = {"@timestamp": timestamp.isoformat(), "host": {"name": hostname}, "system": {"cpu": {"total": {"norm": {"pct": 0.75}}}}}
            lines.extend((json.dumps({"create": {"_index": "metrics-system.cpu-default"}}), json.dumps(doc)))
        response = client.post(host["es"] + "/_bulk?refresh=true", data="\n".join(lines) + "\n",
                               headers={"Content-Type": "application/x-ndjson"}, timeout=30)
        response.raise_for_status()
        assert not response.json()["errors"], "Integration metrics must index successfully"
        def accepted():
            for receipt in (runtime / "receipts").glob("*.json"):
                body = json.loads(receipt.read_text())
                if hostname in body["fields"]["title"]:
                    assert body["class"] == "Incident"
                    assert body["caller"] == cfg["itsm"]["caller"]
                    return True
            return False
        eventually(accepted, "ElastAlert Kafka event-center delivery", seconds=180)
    finally:
        subprocess.run(["docker", "rm", "-f", "event-center-test"], capture_output=True)


if __name__ == "__main__":
    main()
