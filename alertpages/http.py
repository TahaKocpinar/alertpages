from __future__ import annotations

import json
import urllib.error
import urllib.request

from . import __version__

USER_AGENT = f"alertpages/{__version__} (+https://github.com/tahakocp/alertpages)"


class FetchError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def fetch(url: str, timeout: float = 20.0, data: bytes | None = None,
          headers: dict | None = None, redact: str | None = None) -> bytes:
    """GET (or POST when `data` is given). Errors never include `redact`."""
    h = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    shown = url.replace(redact, "***") if redact else url
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", "replace")
        if redact:
            body = body.replace(redact, "***")
        raise FetchError(f"HTTP {e.code} from {shown}: {body}", status=e.code) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = str(getattr(e, "reason", e))
        if redact:
            reason = reason.replace(redact, "***")
        raise FetchError(f"{type(e).__name__} for {shown}: {reason}") from None


def post_json(url: str, payload: dict, timeout: float = 20.0, redact: str | None = None) -> dict:
    raw = fetch(url, timeout=timeout, data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}, redact=redact)
    return json.loads(raw)
