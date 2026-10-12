"""ElastAlert command adapter: match -> durable event queue."""
import sys
from .config import settings
from .events import event, publish


def main():
    if len(sys.argv) < 5:
        raise SystemExit("Required: caller kind host timestamp [parameters ...]")
    caller, kind, host, timestamp, *values = sys.argv[1:]
    params = {"Param" + str(i + 1): value for i, value in enumerate(values)}
    caller = settings()["itsm"].get("caller", caller)
    publish(event(kind, host, timestamp, params, caller=caller))


if __name__ == "__main__":
    main()
