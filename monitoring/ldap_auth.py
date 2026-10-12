import base64
import binascii
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from ldap3 import Connection, Server, Tls, SUBTREE
from ldap3.utils.conv import escape_filter_chars
from .config import secret, settings


def decode(header):
    if not header or not header.startswith("Basic "):
        raise ValueError("Basic authentication required")
    raw = base64.b64decode(header[6:], validate=True).decode("utf-8")
    user, password = raw.split(":", 1)
    if not user or not password:
        raise ValueError("Empty credentials")
    return user, password


def authenticate(user, password, cfg, bind_password, connection=Connection):
    uri = urlsplit(cfg["base"])
    if uri.scheme != "ldaps":
        raise ValueError("LDAP TLS is required")
    tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=cfg["ca_file"])
    server = Server(uri.hostname, port=uri.port or 636, use_ssl=True, tls=tls, connect_timeout=5)
    with connection(server, user=cfg["bind_dn"], password=bind_password,
                    auto_bind=True, receive_timeout=5, auto_referrals=False) as search:
        query = cfg["filter"].replace("{user}", escape_filter_chars(user))
        if not search.search(cfg["base_dn"], query, search_scope=SUBTREE, attributes=["objectClass"], size_limit=2):
            return False
        if len(search.entries) != 1:
            return False
        dn = search.entries[0].entry_dn
    with connection(server, user=dn, password=password, auto_bind=True,
                    receive_timeout=5, auto_referrals=False):
        return True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            return
        try:
            user, password = decode(self.headers.get("Authorization"))
            cfg = settings()["ldap"]
            valid = authenticate(user, password, cfg, secret("ldap-bind-password"))
        except Exception:
            valid = False
        self.send_response(200 if valid else 401)
        self.send_header("Cache-Control", "no-store")
        if not valid:
            self.send_header("WWW-Authenticate", 'Basic realm="Monitoring"')
        self.end_headers()


def main():
    ThreadingHTTPServer((settings()["listen_host"], 8888), Handler).serve_forever()


if __name__ == "__main__":
    main()
