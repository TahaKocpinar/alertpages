"""alertpages command line: fetch -> normalize -> merge -> filter -> relay -> publish."""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__, config, filters, merge, site, state, telegram
from .http import FetchError, fetch
from .sources import REGISTRY


def collect(cfg: dict, now: datetime, fixtures: str | None = None, log=print):
    alerts, status = [], []
    for src in cfg["sources"]:
        kind = src["type"]
        mod = REGISTRY.get(kind)
        name = src.get("name", kind)
        if mod is None:
            raise SystemExit(f"unknown source type {kind!r}; known: {', '.join(REGISTRY)}")
        started = time.monotonic()
        try:
            if fixtures:
                url = str(Path(fixtures) / src.get("fixture", f"{name}"))
                raw = Path(url).read_bytes()
            else:
                url = mod.url(src, now)
                raw = fetch(url, timeout=float(src.get("timeout", 20)))
            items = mod.parse(raw, src)
            alerts.extend(items)
            status.append({"name": name, "type": kind, "ok": True, "count": len(items),
                           "ms": round((time.monotonic() - started) * 1000)})
            log(f"source {name}: {len(items)} alerts")
        except (FetchError, OSError, ValueError, KeyError) as e:
            status.append({"name": name, "type": kind, "ok": False, "error": str(e)[:200]})
            log(f"source {name}: FAILED {e}")
    return alerts, status


def run(args) -> int:
    cfg = config.load(args.config)
    now = datetime.now(timezone.utc) if not args.now else datetime.fromisoformat(args.now).astimezone(timezone.utc)
    raw, status = collect(cfg, now, args.fixtures)
    if not any(s["ok"] for s in status):
        print("every source failed; keeping the previous deployment", file=sys.stderr)
        return 2
    m = cfg.get("merge", {})
    merged = merge.merge(raw, prefer=m.get("prefer"), window_s=m.get("window_seconds", 90),
                         distance_km=m.get("distance_km", 100), mag_delta=m.get("magnitude_delta", 1.0))
    shown = [a for a in merged if filters.matches(a, cfg.get("display", {}), now)]
    shown = shown[: int(cfg["site"].get("max_items", 300))]
    print(f"{len(raw)} reports -> {len(merged)} events after merge -> {len(shown)} shown")

    st = state.load(url=args.state_url, path=args.state_file)
    tg = cfg.get("telegram", {})
    candidates = [a for a in merged if filters.matches(a, tg, now)] if tg else []
    fresh = [a for a in candidates if not st.has(merge.report_ids(a))]
    if st.status == "missing" and not args.send_backlog:
        print(f"state: none published yet; priming with {len(candidates)} events, nothing sent")
        fresh = []
    elif st.status == "unavailable":
        window = timedelta(minutes=float(tg.get("unknown_state_window_minutes", 30)))
        fresh = [a for a in fresh if a.time >= now - window]
        print(f"state: unavailable; only relaying alerts newer than {window}")
    failed = []
    if fresh:
        token = os.environ.get(tg.get("token_env", "TELEGRAM_BOT_TOKEN"))
        chat = os.environ.get(tg.get("chat_id_env", "TELEGRAM_CHAT_ID"))
        if not (token and chat) and not args.dry_run:
            print("telegram: token/chat id env vars not set; printing instead")
        failed = telegram.relay(fresh, token, chat, lang=tg.get("language", "en"),
                                tz_name=cfg["site"].get("timezone"),
                                max_messages=int(tg.get("max_messages_per_run", 10)),
                                dry_run=args.dry_run)
    failed_ids = {i for a in failed for i in merge.report_ids(a)}
    # Only alerts that matched the Telegram rule are recorded: an event that is
    # later revised upwards past the threshold still gets relayed.
    for a in candidates:
        ids = merge.report_ids(a)
        if not failed_ids.intersection(ids):
            st.add(ids, now)
    st.prune(now)
    print(f"telegram: {len(fresh) - len(failed)} relayed, {len(failed)} failed")
    if args.out:
        out = site.write(args.out, shown, status, cfg["site"], st.to_json(), now)
        print(f"site written to {out}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="alertpages", description=__doc__)
    p.add_argument("--version", action="version", version=f"alertpages {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="fetch feeds, relay new alerts, write the site")
    r.add_argument("-c", "--config", help="TOML config (default: USGS M2.5+ and GDACS)")
    r.add_argument("-o", "--out", default="_site", help="output directory (default: _site)")
    r.add_argument("--state-url", help="URL of the previously published state.json")
    r.add_argument("--state-file", help="local state.json (alternative to --state-url)")
    r.add_argument("--dry-run", action="store_true", help="print Telegram messages instead of sending")
    r.add_argument("--send-backlog", action="store_true", help="relay even when no state exists yet")
    r.add_argument("--fixtures", help="read sources from files in this directory (testing)")
    r.add_argument("--now", help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
