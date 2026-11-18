"""USGS earthquake GeoJSON summary feeds or FDSN queries."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from ..model import Alert

FEED = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{feed}.geojson"


def url(opts: dict, now: datetime) -> str:
    return opts.get("url") or FEED.format(feed=opts.get("feed", "2.5_day"))


def parse(raw: bytes, opts: dict | None = None) -> list[Alert]:
    out = []
    for f in json.loads(raw).get("features", []):
        p = f["properties"]
        if p.get("type", "earthquake") != "earthquake":
            continue
        lon, lat, depth = (f.get("geometry") or {}).get("coordinates", [None, None, None])[:3]
        out.append(Alert(
            id=f"usgs:{f['id']}",
            source="usgs",
            kind="earthquake",
            title=p.get("place") or "",
            area=p.get("place") or "",
            time=datetime.fromtimestamp(p["time"] / 1000, tz=timezone.utc),
            lat=lat,
            lon=lon,
            magnitude=p.get("mag"),
            depth_km=depth,
            url=p.get("url") or "",
        ))
    return out
