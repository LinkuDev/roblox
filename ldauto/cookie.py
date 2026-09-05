"""Doc va xac minh cookie .ROBLOSECURITY.

Tach rieng phan doc SQLite + goi API (thuan tuy, test duoc) khoi phan ADB
(nam trong Instance.extract_cookie).
"""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from pathlib import Path

# Roblox gan tien to canh bao truoc gia tri cookie. Gia tri trong DB thuong da
# co san; khi xuat ra file thi bao dam co de nguoi dung dan vao trinh duyet duoc.
WARNING_PREFIX = (
    "_|WARNING:-DO-NOT-SHARE-THIS.--Sharing-this-will-allow-someone-to-log-into-"
    "your-account-and-steal-your-points-and-Robux|_"
)


def ensure_warning_prefix(cookie: str) -> str:
    return cookie if cookie.startswith("_|WARNING") else WARNING_PREFIX + cookie


def read_roblosecurity(db_path: str | Path) -> tuple[str | None, bool]:
    """Doc .ROBLOSECURITY tu mot file Cookies (SQLite Chromium).

    Tra ve (cookie, da_ma_hoa):
      - (chuoi, False): lay duoc plaintext
      - (None,  True) : cookie nam o encrypted_value dang v10 -> chua giai ma
      - (None,  False): khong tim thay cookie trong file nay
    """
    con = sqlite3.connect(str(db_path))
    try:
        # Doc CA hai cot: value (plaintext) va encrypted_value (blob v10).
        # host_key loc ve roblox de khoi vo tinh lay cookie cua trang khac.
        rows = con.execute(
            "SELECT value, encrypted_value FROM cookies "
            "WHERE name = '.ROBLOSECURITY'"
        ).fetchall()
    except sqlite3.Error:
        return None, False
    finally:
        con.close()

    encrypted_seen = False
    for value, enc in rows:
        if value:  # WebView Android thuong luu plaintext o day
            return value, False
        if enc and bytes(enc)[:3] == b"v10":
            encrypted_seen = True
    return None, encrypted_seen


def verify_cookie(cookie: str, timeout: float = 10.0) -> dict | None:
    """Goi API Roblox de xac nhan cookie song. Tra ve {'id','name'} hoac None.

    KHONG tat xac minh TLS (script goc tat -- ho MITM khi gui credential di).
    Thu ca dang tho lan dang co tien to WARNING.
    """
    for c in (cookie, ensure_warning_prefix(cookie)):
        req = urllib.request.Request(
            "https://users.roblox.com/v1/users/authenticated",
            headers={
                "Cookie": f".ROBLOSECURITY={c}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            if data.get("name"):
                return {"id": data.get("id"), "name": data["name"]}
        except Exception:
            continue
    return None
