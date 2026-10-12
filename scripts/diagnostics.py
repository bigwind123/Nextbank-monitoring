"""Print failure categories without publishing runtime settings or secrets."""
import json
import re
import subprocess
import sys
from pathlib import Path
from .platform import ROOT, default_runtime


def main():
    runtime = default_runtime()
    base = ["docker", "compose", "--project-directory", str(ROOT), "--env-file", str(runtime / "compose.env"), "-f", str(ROOT / "compose.yaml")]
    result = subprocess.run(base + ["ps", "--all", "--format", "json"], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        try:
            item = json.loads(line)
            print(json.dumps({k: item.get(k) for k in ("Service", "State", "ExitCode", "Health")}))
        except ValueError:
            pass
    output = subprocess.run(base + ["logs", "--no-color", "--tail", "80"], capture_output=True, text=True).stdout
    for line in output.splitlines():
        if re.search(r"error|exception|failed|denied|invalid|unknown setting|out of memory|cannot|could not|no such|not found|unable", line, re.I):
            line = re.sub(r"[A-Za-z]+://[^\s\"']+", "[address removed]", line)
            line = re.sub(r"(?:\d{1,3}\.){3}\d{1,3}", "[address removed]", line)
            line = re.sub(r"[A-Za-z0-9_+/=-]{24,}", "[value removed]", line)
            line = re.sub(r'(?i)(password|token|api_key|api key|authorization)(\s*[:=]\s*)[^,}\s]+', r'\1\2[removed]', line)
            print(line[:900])


if __name__ == "__main__":
    main()
