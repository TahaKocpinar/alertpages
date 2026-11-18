"""AFAD (Disaster and Emergency Management Presidency, Türkiye) event API.

Times in the API are UTC (verified against EMSC for the same events).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from ..model import Alert, parse_time

BASE = "https://servisnet.afad.gov.tr/apigateway/deprem/apiv2/event/filter"


def url(opts: dict, now: datetime) -> str:
    hours = float(opts.get("lookback_hours", 24))
    q = {
        "start": (now - timedelta(hours=hours)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "end": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "format": "json",
    }
    if "min_magnitude" in opts:
        q["minmag"] = opts["min_magnitude"]
    return opts.get("url") or f"{BASE}?{urlencode(q)}"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse(raw: bytes, opts: dict | None = None) -> list[Alert]:
    out = []
    for e in json.loads(raw):
        eid = str(e["eventID"])
        out.append(Alert(
            id=f"afad:{eid}",
            source="afad",
            kind="earthquake",
            title=e.get("location") or "",
            area=e.get("location") or "",
            time=parse_time(e["date"]),
            lat=_f(e.get("latitude")),
            lon=_f(e.get("longitude")),
            magnitude=_f(e.get("magnitude")),
            depth_km=_f(e.get("depth")),
            url=f"https://deprem.afad.gov.tr/event-detail/{eid}",
        ))
    return out
