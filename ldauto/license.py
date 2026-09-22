"""Kiem tra license truc tuyen (an) truoc khi cho mo app.

Goi GET http://.../api/license/check?key=<KEY>. HTTP 200 -> hop le, cho mo.
Bat ky ket qua khac (khong 200, mat mang, server chet) -> KHONG hop le, khong
cho mo (fail-closed: license phai xac thuc duoc moi chay).
"""

from __future__ import annotations

import urllib.parse
import urllib.request

BASE = "http://31.207.4.14:3301"
CHECK_PATH = "/api/license/check"
DEFAULT_KEY = "3301"


def check(key: str = DEFAULT_KEY, timeout: float = 8.0) -> bool:
    """True neu server tra HTTP 200; nguoc lai (ke ca loi mang) False."""
    url = f"{BASE}{CHECK_PATH}?key={urllib.parse.quote(key)}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return getattr(resp, "status", resp.getcode()) == 200
    except Exception:
        return False
