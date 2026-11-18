from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources


@lru_cache(maxsize=1)
def strings() -> dict:
    return json.loads(resources.files("alertpages").joinpath("web/i18n.json").read_text("utf-8"))


def t(lang: str) -> dict:
    s = strings()
    return s.get(lang) or s["en"]
