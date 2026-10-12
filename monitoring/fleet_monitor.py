import json
import logging
import sqlite3
import time
from pathlib import Path
from .config import settings, session, request
from .events import event, now, producer, publish


def fetch_agents(client, base):
    page = 1
    result = []
    while True:
        data = request(client, "GET", base, "/api/fleet/agents", params={"page": page, "perPage": 100})
        items = data.get("items", data.get("list", []))
        result.extend(items)
        if len(result) >= data.get("total", len(result)) or not items:
            return result
        page += 1


def transition(agent, previous):
    status = agent.get("status", "unknown")
    if status == previous or status not in {"error", "degraded", "offline"}:
        return None
    host = agent.get("local_metadata", {}).get("host", {}).get("hostname", agent["id"])
    return event("Elastic_Agent_Status", host, now(), {"Param1": status})


def main():
    logging.basicConfig(level=logging.INFO)
    cfg = settings()
    path = Path(cfg["state_dir"])
    path.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path / "agents.db")
    db.execute("CREATE TABLE IF NOT EXISTS agents (id TEXT PRIMARY KEY, status TEXT NOT NULL)")
    client, queue = session("kibana"), producer()
    while True:
        try:
            for agent in fetch_agents(client, cfg["kibana"]):
                previous = db.execute("SELECT status FROM agents WHERE id=?", (agent["id"],)).fetchone()
                payload = transition(agent, previous[0] if previous else None)
                if payload:
                    publish(payload, queue)
                db.execute("INSERT OR REPLACE INTO agents VALUES (?,?)", (agent["id"], agent.get("status", "unknown")))
                db.commit()
        except Exception as exc:
            logging.warning("Fleet check failed: %s", type(exc).__name__)
        time.sleep(cfg.get("agent_check_seconds", 60))


if __name__ == "__main__":
    main()
