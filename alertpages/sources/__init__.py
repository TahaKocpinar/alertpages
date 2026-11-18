"""Feed adapters. Each module exposes `url(opts, now)` and `parse(raw, opts)`."""

from __future__ import annotations

from . import afad, cap, emsc, gdacs, kandilli, rss, usgs

REGISTRY = {
    "afad": afad,
    "kandilli": kandilli,
    "emsc": emsc,
    "usgs": usgs,
    "gdacs": gdacs,
    "cap": cap,
    "rss": rss,
}
