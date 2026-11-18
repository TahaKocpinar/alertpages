"""Write the static site: PWA shell + alerts.json + feed.xml + state.json."""

from __future__ import annotations

import html
import json
from datetime import datetime
from email.utils import format_datetime
from importlib import resources
from pathlib import Path

from . import __version__
from .i18n import t
from .model import Alert, iso

ASSETS = ["index.html", "app.js", "style.css", "sw.js", "icon.svg", "i18n.json"]


def write(out: str | Path, alerts: list[Alert], sources: list[dict], site: dict,
          state: dict, now: datetime) -> Path:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    title = site.get("title", "Alert relay")
    langs = site.get("languages", ["en"])
    default = site.get("default_language", langs[0])
    web = resources.files("alertpages").joinpath("web")
    for name in ASSETS:
        data = web.joinpath(name).read_text("utf-8")
        if name == "index.html":
            data = (data.replace("{{TITLE}}", html.escape(title))
                        .replace("{{LANG}}", default)
                        .replace("{{DIR}}", t(default)["dir"])
                        .replace("{{DESCRIPTION}}", html.escape(site.get("description", title))))
        if name == "sw.js":
            # bump the cache name on every release so clients pick up new assets
            data = data.replace("{{VERSION}}", __version__)
        (out / name).write_text(data, "utf-8")
    manifest = {
        "name": title, "short_name": site.get("short_name", title[:12]),
        "start_url": "./", "scope": "./", "display": "standalone",
        "background_color": "#111418", "theme_color": "#b3261e", "lang": default,
        "dir": t(default)["dir"],
        "icons": [{"src": "icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}],
    }
    (out / "manifest.webmanifest").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), "utf-8")
    payload = {
        "generated": iso(now),
        "generator": f"alertpages {__version__}",
        "site": {"title": title, "languages": langs, "default_language": default,
                 "timezone": site.get("timezone", "UTC"),
                 "refresh_minutes": site.get("refresh_minutes", 5)},
        "sources": sources,
        "alerts": [a.to_json() for a in alerts],
    }
    (out / "alerts.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), "utf-8")
    (out / "feed.xml").write_text(rss(alerts, title, site.get("url", ""), default, now), "utf-8")
    (out / "state.json").write_text(json.dumps(state, indent=1), "utf-8")
    (out / ".nojekyll").write_text("", "utf-8")
    return out


def rss(alerts: list[Alert], title: str, link: str, lang: str, now: datetime) -> str:
    s = t(lang)
    items = []
    for a in alerts[:100]:
        head = s["kind"].get(a.kind, s["kind"]["other"])
        if a.kind == "earthquake" and a.magnitude is not None:
            head = f"M{a.magnitude:.1f} {head}"
        items.append(
            "<item>"
            f"<title>{html.escape(head + ' — ' + (a.area or a.title))}</title>"
            f"<link>{html.escape(a.url)}</link>"
            f"<guid isPermaLink=\"false\">{html.escape(a.id)}</guid>"
            f"<pubDate>{format_datetime(a.time)}</pubDate>"
            f"<description>{html.escape(a.title)}</description>"
            + (f"<georss:point>{a.lat} {a.lon}</georss:point>" if a.lat is not None else "")
            + "</item>"
        )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<rss version="2.0" xmlns:georss="http://www.georss.org/georss"><channel>'
        f"<title>{html.escape(title)}</title><link>{html.escape(link)}</link>"
        f"<description>{html.escape(title)}</description><language>{lang}</language>"
        f"<lastBuildDate>{format_datetime(now)}</lastBuildDate>"
        + "".join(items) + "</channel></rss>\n"
    )
