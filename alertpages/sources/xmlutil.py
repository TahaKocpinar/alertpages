from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime

from ..model import parse_time


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child(el, name: str):
    """First direct child whose local name is `name` (namespace-agnostic)."""
    for c in el:
        if local(c.tag) == name:
            return c
    return None


def text(el, name: str, default: str = "") -> str:
    c = child(el, name)
    return (c.text or "").strip() if c is not None and c.text else default


def find_all(el, name: str):
    return [c for c in el.iter() if local(c.tag) == name]


def when(value: str):
    if not value:
        return None
    try:
        return parse_time(value)
    except ValueError:
        try:
            return parsedate_to_datetime(value).astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None


def parse_xml(raw: bytes):
    return ET.fromstring(raw)
