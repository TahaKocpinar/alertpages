"""Which alerts were already relayed. The state lives inside the published site
(state.json), so no commits, caches or databases are needed."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from .http import FetchError, fetch
from .model import iso, parse_time

KEEP_DAYS = 14


class State:
    def __init__(self, seen: dict[str, str] | None = None, status: str = "ok"):
        self.seen = seen or {}
        # ok | missing (first deploy: prime, send nothing) | unavailable (send only fresh alerts)
        self.status = status

    def has(self, ids) -> bool:
        return any(i in self.seen for i in ids)

    def add(self, ids, now: datetime) -> None:
        for i in ids:
            self.seen.setdefault(i, iso(now))

    def prune(self, now: datetime) -> None:
        cutoff = now - timedelta(days=KEEP_DAYS)
        self.seen = {k: v for k, v in self.seen.items() if parse_time(v) >= cutoff}

    def to_json(self) -> dict:
        return {"version": 1, "seen": dict(sorted(self.seen.items()))}


def load(url: str | None = None, path: str | None = None) -> State:
    try:
        if path:
            with open(path, encoding="utf-8") as fh:
                return State(json.load(fh).get("seen", {}))
        if url:
            return State(json.loads(fetch(url, timeout=15)).get("seen", {}))
    except FileNotFoundError:
        return State(status="missing")
    except FetchError as e:
        return State(status="missing" if e.status == 404 else "unavailable")
    except (ValueError, KeyError):
        return State(status="unavailable")
    return State(status="missing")
