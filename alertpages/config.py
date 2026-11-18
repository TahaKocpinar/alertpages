from __future__ import annotations

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None

DEFAULT = {
    "site": {"title": "Disaster alert relay", "languages": ["en"], "max_items": 300},
    "sources": [{"type": "usgs", "feed": "2.5_day"}, {"type": "gdacs"}],
    "display": {"max_age_hours": 72},
    "telegram": {},
}


def load(path: str | None) -> dict:
    if not path:
        return DEFAULT
    if tomllib is None:
        raise SystemExit("Python 3.11+ is required to read TOML config files")
    with open(path, "rb") as fh:
        cfg = tomllib.load(fh)
    for key, value in DEFAULT.items():
        cfg.setdefault(key, value)
    return cfg
