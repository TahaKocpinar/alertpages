"""Push alerts to a Telegram chat or channel via the Bot API.

The bot token is read from an environment variable (TELEGRAM_BOT_TOKEN by
default, stored as a GitHub Actions secret) and is never written to output.
"""

from __future__ import annotations

import html
import time
from datetime import timezone, tzinfo

from .http import FetchError, post_json
from .i18n import t
from .model import Alert

API = "https://api.telegram.org/bot{token}/sendMessage"
ICON = {"extreme": "🟥", "severe": "🟧", "moderate": "🟨", "minor": "🟩", "unknown": "⬜"}


def _tz(name: str | None) -> tzinfo:
    if not name or name.upper() == "UTC":
        return timezone.utc
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:  # missing tzdata (e.g. Windows without the tzdata package)
        return timezone.utc


def format_alert(a: Alert, lang: str = "en", tz_name: str | None = None) -> str:
    s = t(lang)
    tz = _tz(tz_name)
    local = a.time.astimezone(tz)
    head = s["kind"].get(a.kind, s["kind"]["other"])
    if a.kind == "earthquake" and a.magnitude is not None:
        head = f"{s['magnitude']}{a.magnitude:.1f} {head}"
    lines = [f"{ICON.get(a.severity, '⬜')} <b>{html.escape(head)}</b> — {html.escape(a.area or a.title)}"]
    lines.append(f"🕒 {local:%Y-%m-%d %H:%M} ({local.tzname() or 'UTC'})")
    detail = []
    if a.depth_km is not None:
        detail.append(f"{s['depth']} {a.depth_km:.0f} {s['km']}")
    if a.kind != "earthquake":
        detail.append(s["severity"].get(a.severity, a.severity))
    if a.expires:
        detail.append(f"{s['expires']} {a.expires.astimezone(tz):%Y-%m-%d %H:%M}")
    srcs = []
    for r in a.reports or [a.report()]:
        label = r["source"].upper() if len(r["source"]) <= 5 else r["source"].title()
        if r.get("magnitude") is not None and a.kind == "earthquake":
            label += f" {r['magnitude']:.1f}"
        srcs.append(label)
    detail.append(f"{s['sources']}: {', '.join(srcs)}")
    lines.append(" · ".join(detail))
    if a.url:
        lines.append(html.escape(a.url))
    return "\n".join(lines)


def send(token: str, chat_id: str, text: str, retries: int = 2) -> None:
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True}
    for attempt in range(retries + 1):
        try:
            post_json(API.format(token=token), payload, redact=token)
            return
        except FetchError as e:
            if e.status == 429 and attempt < retries:
                time.sleep(5 * (attempt + 1))
                continue
            raise


def relay(alerts: list[Alert], token: str | None, chat_id: str | None, lang: str = "en",
          tz_name: str | None = None, max_messages: int = 10, dry_run: bool = False,
          log=print) -> list[Alert]:
    """Send alerts oldest-first. Returns the alerts that failed to send (to be
    retried next run). Alerts dropped by `max_messages` count as handled."""
    failed = []
    queue = sorted(alerts, key=lambda a: a.time)
    if len(queue) > max_messages:
        # keep the strongest, but still post them in time order
        rank = {"extreme": 4, "severe": 3, "moderate": 2, "minor": 1, "unknown": 0}
        keep = sorted(queue, key=lambda a: (rank.get(a.severity, 0), a.magnitude or 0), reverse=True)[:max_messages]
        log(f"telegram: {len(queue)} new alerts, sending the {max_messages} most severe")
        queue = sorted(keep, key=lambda a: a.time)
    for a in queue:
        text = format_alert(a, lang, tz_name)
        if dry_run or not token or not chat_id:
            log("telegram (dry run):\n" + text)
            continue
        try:
            send(token, chat_id, text)
            time.sleep(1.1)  # stay under Telegram's ~1 msg/s per chat limit
        except FetchError as e:
            log(f"telegram: send failed, will retry next run: {e}")
            failed.append(a)
    return failed
