"""GDACS (Global Disaster Alert and Coordination System) RSS feed.

Alert level maps to severity: Green -> minor, Orange -> severe, Red -> extreme.
The id includes the alert level, so an escalation (Green -> Orange) is a new
alert and gets relayed again.
"""

from __future__ import annotations

from datetime import datetime

from ..model import Alert
from .xmlutil import child, parse_xml, text, when

URL = "https://www.gdacs.org/xml/rss.xml"
KINDS = {"EQ": "earthquake", "TC": "cyclone", "FL": "flood", "VO": "volcano",
         "DR": "drought", "WF": "wildfire", "TS": "tsunami"}
LEVELS = {"green": "minor", "orange": "severe", "red": "extreme"}


def url(opts: dict, now: datetime) -> str:
    return opts.get("url") or URL


def parse(raw: bytes, opts: dict | None = None) -> list[Alert]:
    root = parse_xml(raw)
    channel = child(root, "channel")
    out = []
    for item in channel.findall("item") if channel is not None else []:
        etype = text(item, "eventtype")
        level = text(item, "alertlevel").lower()
        if text(item, "iscurrent", "true").lower() != "true":
            continue
        point = child(item, "Point")
        lat = lon = None
        if point is not None:
            lat, lon = float(text(point, "lat")), float(text(point, "long"))
        sev = child(item, "severity")
        mag = None
        if etype == "EQ" and sev is not None and sev.get("unit") == "M":
            mag = float(sev.get("value"))
        guid = text(item, "guid") or f"{etype}{text(item, 'eventid')}"
        out.append(Alert(
            id=f"gdacs:{guid}:{level or 'na'}",
            source="gdacs",
            kind=KINDS.get(etype, "other"),
            title=text(item, "title"),
            area=text(item, "country"),
            time=when(text(item, "fromdate")) or when(text(item, "pubDate")),
            lat=lat,
            lon=lon,
            magnitude=mag,
            severity=LEVELS.get(level, "unknown"),
            url=text(item, "link"),
        ))
    return out
