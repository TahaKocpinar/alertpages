"""Kandilli Observatory (KOERI) "Son Depremler" list (lst0.asp).

The page is a windows-1254 <pre> block; times are Turkish local time (UTC+3,
no DST since 2016). The endpoint is often unreachable from outside Türkiye,
including GitHub-hosted runners; failures are reported, not fatal.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from ..model import Alert

URL = "http://www.koeri.boun.edu.tr/scripts/lst0.asp"
TRT = timezone(timedelta(hours=3))

LINE = re.compile(
    r"^(\d{4}\.\d{2}\.\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+"
    r"(\d+(?:\.\d+)?)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.*?)\s*$"
)
QUALITY = re.compile(r"\s+(İlksel|Ilksel|Ýlksel|REVIZE\d*|REVİZE\d*)(\s*\(.*\))?\s*$", re.I)


def url(opts: dict, now: datetime) -> str:
    return opts.get("url") or URL


def _mag(v: str):
    try:
        return float(v)
    except ValueError:
        return None


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("windows-1254", "replace")


def parse(raw: bytes, opts: dict | None = None) -> list[Alert]:
    out = []
    for line in _decode(raw).splitlines():
        m = LINE.match(line.strip())
        if not m:
            continue
        d, t, lat, lon, depth, md, ml, mw, rest = m.groups()
        q = QUALITY.search(" " + rest)
        place = rest[: q.start() - 1].strip() if q and q.start() > 0 else rest.strip()
        revised = bool(q and q.group(1).upper().startswith("REV"))
        when = datetime.strptime(f"{d} {t}", "%Y.%m.%d %H:%M:%S").replace(tzinfo=TRT)
        mag = next((x for x in (_mag(mw), _mag(ml), _mag(md)) if x is not None), None)
        native = f"{when.astimezone(timezone.utc):%Y%m%d%H%M%S}_{float(lat):.2f}_{float(lon):.2f}"
        out.append(Alert(
            id=f"kandilli:{native}",
            source="kandilli",
            kind="earthquake",
            title=place + (" (revised)" if revised else ""),
            area=place,
            time=when.astimezone(timezone.utc),
            lat=float(lat),
            lon=float(lon),
            magnitude=mag,
            depth_km=float(depth),
            url=URL,
        ))
    return out
