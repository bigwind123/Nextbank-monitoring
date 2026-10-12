import ast
import json
import re
import subprocess
from pathlib import Path
import yaml
from .platform import ROOT


def paths():
    if (ROOT / ".git").exists():
        result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
        return [ROOT / p.decode() for p in result.stdout.split(b"\0") if p]
    return [p for p in ROOT.rglob("*") if p.is_file() and not any(part.startswith(".") or part == "__pycache__" for part in p.relative_to(ROOT).parts)]


def main():
    count = 0
    for path in paths():
        relative = path.relative_to(ROOT)
        if any(part in {".runtime", ".local", ".venv", "__pycache__"} for part in relative.parts):
            raise ValueError("Runtime or local data tracked in Git")
        if path.suffix in {".pem", ".key", ".p12", ".env", ".db"}:
            raise ValueError("Sensitive artifact is tracked")
        text = path.read_text(encoding="utf-8")
        if re.search(r"-----BEGIN [A-Z ]*(?:PRIVATE KEY|CERTIFICATE)-----", text):
            raise ValueError("Embedded key or certificate")
        if path.suffix in {".json"}:
            json.loads(text)
        if path.suffix in {".yaml", ".yml"} or path.name.endswith(".yaml.disabled"):
            list(yaml.safe_load_all(text))
        if path.suffix == ".py":
            ast.parse(text)
        if path.suffix in {".yaml", ".yml", ".json", ".conf"} and re.search(r"https?://[A-Za-z0-9]", text):
            raise ValueError("Literal service address in deployment configuration")
        count += 1
    catalog = json.loads((ROOT / "config" / "rule-catalog.json").read_text())
    assert len(catalog) == 76
    assert len({item["id"] for item in catalog}) == len(catalog)
    from monitoring.strategies import AlertHandler
    known = AlertHandler({}).handlers
    assert all(item["strategy"] in known or item["strategy"] == "TEST" for item in catalog), "Unknown alert strategy"
    print("Source, configuration and publication validation passed:", count, "files")


if __name__ == "__main__":
    main()
