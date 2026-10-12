"""External event-center contract used only by the isolated integration test."""
import ipaddress
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

PATH = Path("/runtime")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        data = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
        cfg = json.loads((PATH / "platform.json").read_text())["itsm"]
        expected = (PATH / "secrets" / "itsm-password").read_text().strip()
        if data.get("auth_user", [None])[0] != cfg["user"] or data.get("auth_pwd", [None])[0] != expected:
            self.send_response(403)
            self.end_headers()
            return
        payload = json.loads(data["json_data"][0])
        event_id = self.headers["Idempotency-Key"]
        folder = PATH / "receipts"
        folder.mkdir(exist_ok=True)
        receipt = folder / (event_id + ".json")
        if not receipt.exists():
            receipt.write_text(json.dumps(payload))
            receipt.chmod(0o644)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"code": 0}).encode())


HTTPServer((str(ipaddress.IPv4Address(0)), 8089), Handler).serve_forever()
