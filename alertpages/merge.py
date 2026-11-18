"""Collapse reports of the same earthquake from different agencies into one alert.

Two reports belong to the same event when they are within `window_s` seconds,
`distance_km` kilometres and `mag_delta` magnitude units of each other and come
from different sources (one agency never reports the same quake twice in one
fetch, but aftershock sequences produce many nearby events).
"""

from __future__ import annotations

from dataclasses import replace

from .model import SEVERITY_ORDER, Alert, haversine_km

DEFAULT_PREFER = ["afad", "kandilli", "emsc", "usgs", "gdacs"]


def quake_severity(mag: float | None) -> str:
    if mag is None:
        return "unknown"
    if mag >= 6.5:
        return "extreme"
    if mag >= 5.5:
        return "severe"
    if mag >= 4.0:
        return "moderate"
    return "minor"


def _match(a: Alert, b: Alert, window_s: float, distance_km: float, mag_delta: float) -> float | None:
    dt = abs((a.time - b.time).total_seconds())
    if dt > window_s:
        return None
    if None in (a.lat, a.lon, b.lat, b.lon):
        return None
    dist = haversine_km(a.lat, a.lon, b.lat, b.lon)
    if dist > distance_km:
        return None
    if a.magnitude is not None and b.magnitude is not None and abs(a.magnitude - b.magnitude) > mag_delta:
        return None
    return dt / window_s + dist / distance_km  # lower is better


def merge(alerts: list[Alert], prefer: list[str] | None = None, window_s: float = 90,
          distance_km: float = 100, mag_delta: float = 1.0) -> list[Alert]:
    prefer = prefer or DEFAULT_PREFER
    rank = {s: i for i, s in enumerate(prefer)}
    quakes = sorted((a for a in alerts if a.kind == "earthquake"), key=lambda a: a.time)
    others = [a for a in alerts if a.kind != "earthquake"]

    clusters: list[list[Alert]] = []
    for a in quakes:
        best, best_score = None, None
        for c in clusters:
            if any(x.source == a.source for x in c):
                continue
            scores = [_match(a, x, window_s, distance_km, mag_delta) for x in c]
            if any(s is None for s in scores):
                continue
            score = min(scores)
            if best_score is None or score < best_score:
                best, best_score = c, score
        if best is None:
            clusters.append([a])
        else:
            best.append(a)

    merged = []
    for c in clusters:
        c.sort(key=lambda x: rank.get(x.source, len(rank)))
        primary = c[0]
        sev = max((x.severity for x in c), key=SEVERITY_ORDER.index)
        sev = max(sev, quake_severity(primary.magnitude), key=SEVERITY_ORDER.index)
        merged.append(replace(primary, severity=sev, reports=[x.report() for x in c]))
    for a in others:
        if not a.reports:
            a = replace(a, reports=[a.report()])
        merged.append(a)
    merged.sort(key=lambda a: a.time, reverse=True)
    return merged


def report_ids(alert: Alert) -> list[str]:
    return [r["id"] for r in alert.reports] or [alert.id]
