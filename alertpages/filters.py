"""Decide which alerts to show on the page and which to push to Telegram."""

from __future__ import annotations

from datetime import datetime, timedelta

from .model import SEVERITY_ORDER, Alert, haversine_km


def matches(alert: Alert, rule: dict, now: datetime) -> bool:
    """Rule keys (all optional): kinds, min_magnitude, min_severity,
    max_age_hours, bbox [min_lon, min_lat, max_lon, max_lat],
    regions [{name, lat, lon, radius_km}]."""
    if rule.get("kinds") and alert.kind not in rule["kinds"]:
        return False
    if "max_age_hours" in rule and alert.time < now - timedelta(hours=float(rule["max_age_hours"])):
        return False
    if alert.kind == "earthquake":
        if "min_magnitude" in rule:
            big = alert.magnitude is not None and alert.magnitude >= float(rule["min_magnitude"])
            # A GDACS Orange/Red impact estimate lets a quake through even
            # below the magnitude cut-off (shallow quake under a dense city).
            impact = any(r.get("severity") in ("severe", "extreme") for r in alert.reports)
            if not big and not impact:
                return False
    elif "min_severity" in rule:
        if SEVERITY_ORDER.index(alert.severity) < SEVERITY_ORDER.index(rule["min_severity"].lower()):
            return False
    if rule.get("bbox") or rule.get("regions"):
        return in_area(alert, rule)
    return True


def in_area(alert: Alert, rule: dict) -> bool:
    if alert.lat is None or alert.lon is None:
        # Area-only alerts (CAP without geometry) can only be matched by name.
        names = [r.get("name", "").lower() for r in rule.get("regions", [])]
        return any(n and n in alert.area.lower() for n in names)
    bbox = rule.get("bbox")
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        if min_lon <= alert.lon <= max_lon and min_lat <= alert.lat <= max_lat:
            return True
    for r in rule.get("regions", []):
        if haversine_km(alert.lat, alert.lon, r["lat"], r["lon"]) <= float(r["radius_km"]):
            return True
    return False
