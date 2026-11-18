"""EMSC / seismicportal.eu FDSN event service (JSON)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from ..model import Alert, parse_time

BASE = "https://www.seismicportal.eu/fdsnws/event/1/query"


def url(opts: dict, now: datetime) -> str:
    if opts.get("url"):
        return opts["url"]
    hours = float(opts.get("lookback_hours", 24))
    q = {
        "format": "json",
        "limit": int(opts.get("limit", 500)),
        "start": (now - timedelta(hours=hours)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if "min_magnitude" in opts:
        q["minmag"] = opts["min_magnitude"]
    if "bbox" in opts:
        q["minlon"], q["minlat"], q["maxlon"], q["maxlat"] = opts["bbox"]
    return f"{BASE}?{urlencode(q)}"


def parse(raw: bytes, opts: dict | None = None) -> list[Alert]:
    out = []
    for f in json.loads(raw).get("features", []):
        p = f["properties"]
        unid = p.get("unid") or f.get("id")
        out.append(Alert(
            id=f"emsc:{unid}",
            source="emsc",
            kind="earthquake",
            title=(p.get("flynn_region") or "").title(),
            area=(p.get("flynn_region") or "").title(),
            time=parse_time(p["time"]),
            lat=p.get("lat"),
            lon=p.get("lon"),
            magnitude=p.get("mag"),
            depth_km=p.get("depth"),
            url=f"https://www.seismicportal.eu/eventdetails.html?unid={unid}",
        ))
    return out
