import argparse
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from .config import settings, session, request, secret


def utc():
    return datetime.now(timezone.utc).isoformat()


def ingest(client, cfg, dataset, documents):
    if not documents:
        return
    index = "logs-" + dataset + "-default"
    lines = []
    for doc in documents:
        doc.setdefault("@timestamp", utc())
        event_id = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
        lines.extend((json.dumps({"create": {"_index": index, "_id": event_id}}), json.dumps(doc)))
    result = request(client, "POST", cfg["es"], "/_bulk", data="\n".join(lines) + "\n",
                     headers={"Content-Type": "application/x-ndjson"})
    if any(item["create"]["status"] not in (200, 201, 409) for item in result.get("items", [])):
        raise ValueError("Collector indexing failed")


def f5(client, cfg):
    data = request(client, "GET", cfg["base"], "/mgmt/tm/ltm/pool")
    documents = []
    for pool in data.get("items", []):
        name = pool["fullPath"]
        token = "~" + name.strip("/").replace("/", "~")
        members = request(client, "GET", cfg["base"], "/mgmt/tm/ltm/pool/" + token + "/members")
        stats = request(client, "GET", cfg["base"], "/mgmt/tm/ltm/pool/" + token + "/stats")
        for member in members.get("items", []):
            documents.append({"@timestamp": utc(), "f5": {"pool": name, "member": member["name"],
                "state": member.get("state"), "session": member.get("session"), "statistics": stats.get("entries", {})}})
    return documents


def deepsecurity(client, cfg):
    result = request(client, "GET", cfg["base"], "/api/computers")
    return [{"@timestamp": utc(), "host": {"name": computer.get("hostName", str(computer["ID"]))},
             "deepsecurity": {"computerStatus": computer.get("computerStatus", {})}}
            for computer in result.get("computers", [])]


def security_events(cfg):
    import pyodbc
    queries = {
        "antimalware": "SELECT a.AntiMalwareEventID, a.LogDate, b.Hostname, a.MalwareName FROM dbo.antimalwareevents a JOIN dbo.hosts b ON a.hostid=b.hostid WHERE a.LogDate > ?",
        "integrity": "SELECT a.*, b.Hostname FROM dbo.integrityevents a JOIN dbo.hosts b ON a.hostid=b.hostid WHERE a.LogDate > ?",
        "intrusion": "SELECT a.*, b.Hostname FROM dbo.intrunsionpreventtionevents a JOIN dbo.hosts b ON a.hostid=b.hostid WHERE a.LogDate > ?",
    }
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cfg.get("lookback_minutes", 15))
    records = []
    with pyodbc.connect(secret("security-odbc"), timeout=10) as connection:
        cursor = connection.cursor()
        cursor.timeout = 30
        for kind, sql in queries.items():
            cursor.execute(sql, cutoff)
            keys = [field[0] for field in cursor.description]
            for row in cursor:
                doc = dict(zip(keys, row))
                timestamp = doc.get("LogDate", cutoff)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                records.append({"@timestamp": timestamp.isoformat(), "EventType": kind,
                                "security": {k: v.isoformat() if isinstance(v, datetime) else v for k, v in doc.items()}})
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["f5", "deepsecurity", "security-events"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    cfg = settings()
    external = cfg["collectors"][args.kind]
    client = requests.Session()
    client.verify = external.get("ca_file") or True
    if args.kind == "f5":
        client.auth = (external["user"], secret("f5-password"))
    elif args.kind == "deepsecurity":
        client.headers.update({"api-secret-key": secret("security-api-key"), "api-version": "v1"})
    sink = session()
    while True:
        try:
            docs = security_events(external) if args.kind == "security-events" else globals()[args.kind](client, external)
            ingest(sink, cfg, args.kind, docs)
            logging.info("Collector indexed %d documents", len(docs))
        except Exception as exc:
            logging.error("Collector failed: %s", type(exc).__name__)
        time.sleep(external.get("interval_seconds", 60))


if __name__ == "__main__":
    main()
