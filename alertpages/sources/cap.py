"""CAP 1.2 alerts: Atom/RSS feeds with cap:* entries (e.g. MeteoAlarm) or a
single <alert> document. Only status=Actual and unexpired alerts are kept.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..model import Alert
from .xmlutil import child, find_all, local, parse_xml, text, when


def url(opts: dict, now: datetime) -> str:
    if not opts.get("url"):
        raise ValueError("cap source needs a `url`")
    return opts["url"]


def _centroid(area) -> tuple[float | None, float | None]:
    if area is None:
        return None, None
    circle = text(area, "circle")
    if circle:
        latlon = circle.split()[0].split(",")
        return float(latlon[0]), float(latlon[1])
    poly = text(area, "polygon")
    if poly:
        pts = [tuple(map(float, p.split(","))) for p in poly.split()]
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    return None, None


def _alert_doc(root, opts, now) -> list[Alert]:
    if text(root, "status", "Actual") != "Actual" or text(root, "msgType") == "Cancel":
        return []
    out = []
    ident = text(root, "identifier")
    for i, info in enumerate(c for c in root if local(c.tag) == "info"):
        lang = text(info, "language", "en")
        want = opts.get("language")
        if want and not lang.lower().startswith(want.lower()):
            continue
        expires = when(text(info, "expires"))
        if expires and expires < now:
            continue
        area = child(info, "area")
        lat, lon = _centroid(area)
        out.append(Alert(
            id=f"cap:{ident}:{i}",
            source=opts.get("name", "cap"),
            kind=opts.get("kind", "other"),
            title=text(info, "headline") or text(info, "event"),
            area=text(area, "areaDesc") if area is not None else "",
            time=when(text(info, "onset")) or when(text(info, "effective")) or when(text(root, "sent")),
            lat=lat, lon=lon,
            severity=text(info, "severity", "Unknown").lower(),
            url=text(info, "web") or opts.get("link", ""),
            expires=expires,
        ))
    return out


def parse(raw: bytes, opts: dict | None = None, now: datetime | None = None) -> list[Alert]:
    opts = opts or {}
    now = now or datetime.now(timezone.utc)
    root = parse_xml(raw)
    if local(root.tag) == "alert":
        return _alert_doc(root, opts, now)
    out = []
    for e in find_all(root, "entry") + find_all(root, "item"):
        if text(e, "status", "Actual") != "Actual" or text(e, "message_type") == "Cancel":
            continue
        expires = when(text(e, "expires"))
        if expires and expires < now:
            continue
        ident = text(e, "identifier") or text(e, "id") or text(e, "guid")
        area = text(e, "areaDesc")
        link = ""
        for l in e:
            if local(l.tag) == "link":
                link = l.get("href") or (l.text or "").strip()
                if l.get("rel") in (None, "alternate") and link:
                    break
        out.append(Alert(
            id=f"{opts.get('name', 'cap')}:{ident}:{area}",
            source=opts.get("name", "cap"),
            kind=opts.get("kind", "other"),
            title=text(e, "title") or text(e, "event"),
            area=area,
            time=when(text(e, "onset")) or when(text(e, "effective")) or when(text(e, "sent")),
            severity=text(e, "severity", "Unknown").lower(),
            url=link,
            expires=expires,
        ))
    return out
