"""Plain RSS 2.0 / Atom feed (announcements, bulletins). Every item is one alert."""

from __future__ import annotations

from datetime import datetime, timezone

from ..model import Alert
from .xmlutil import find_all, local, parse_xml, text, when


def url(opts: dict, now: datetime) -> str:
    if not opts.get("url"):
        raise ValueError("rss source needs a `url`")
    return opts["url"]


def parse(raw: bytes, opts: dict | None = None) -> list[Alert]:
    opts = opts or {}
    root = parse_xml(raw)
    name = opts.get("name", "rss")
    out = []
    for e in find_all(root, "item") + find_all(root, "entry"):
        link = text(e, "link")
        for l in e:
            if local(l.tag) == "link" and l.get("href"):
                link = l.get("href")
                break
        ident = text(e, "guid") or text(e, "id") or link or text(e, "title")
        t = when(text(e, "pubDate")) or when(text(e, "updated")) or when(text(e, "published"))
        out.append(Alert(
            id=f"{name}:{ident}",
            source=name,
            kind=opts.get("kind", "other"),
            title=text(e, "title"),
            time=t or datetime.now(timezone.utc),
            severity=opts.get("severity", "unknown"),
            url=link,
        ))
    return out
