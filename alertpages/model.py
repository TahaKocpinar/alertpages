from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

SEVERITY_ORDER = ["unknown", "minor", "moderate", "severe", "extreme"]


@dataclass
class Alert:
    """One normalized alert. Times are always timezone-aware UTC."""

    id: str  # "<source>:<native id>"
    source: str
    kind: str  # earthquake, weather, flood, cyclone, wildfire, volcano, drought, other
    title: str
    time: datetime
    lat: float | None = None
    lon: float | None = None
    magnitude: float | None = None
    depth_km: float | None = None
    severity: str = "unknown"
    area: str = ""
    url: str = ""
    expires: datetime | None = None
    # Filled by merge(): every source that reported this event.
    reports: list[dict] = field(default_factory=list)

    def to_json(self) -> dict:
        d = asdict(self)
        d["time"] = iso(self.time)
        d["expires"] = iso(self.expires) if self.expires else None
        if not d["reports"]:
            d["reports"] = [self.report()]
        return d

    def report(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "time": iso(self.time),
            "magnitude": self.magnitude,
            "severity": self.severity,
            "url": self.url,
        }


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(value: str, default_tz=timezone.utc) -> datetime:
    """Parse ISO-8601-ish timestamps; naive values get `default_tz`."""
    v = value.strip().replace(" ", "T", 1)
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    # Python < 3.11 cannot parse arbitrary fractional digits; normalise to 6.
    if "." in v:
        head, _, rest = v.partition(".")
        digits = "".join(c for c in rest if c.isdigit())
        tail = rest[len(digits):]
        v = f"{head}.{(digits + '000000')[:6]}{tail}"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz)
    return dt.astimezone(timezone.utc)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
