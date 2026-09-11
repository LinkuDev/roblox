"""Ghi nhat ky hoat dong lam viec ve server, de bao cao nang suat.

Muc dich: theo doi cong cu chay tren may nhan vien -- mo luc nao, chay bao lau,
lam duoc bao nhieu acc moi phien -- de danh gia nang suat.

Ky thuat:
- Chay o thread nen, khong chan GUI.
- Nuot moi loi mang (mat mang / server chet / URL sai) -> app van chay binh
  thuong. Day la robustness, khong phai de che giau.

LUU Y PHAP LY: nen bao truoc cho nhan vien rang cong cu co ghi nhan hoat dong
(mot dong trong noi quy / trong app). Xem nhan _build_status trong main.py.
"""

from __future__ import annotations

import getpass
import json
import socket
import threading
import time
import urllib.request

# === Dat IP VPS that vao day TRUOC khi build ===
LOG_URL = "http://<IP_VPS>:3301/api/logs"
SERVICE = "roblox-farm-gui"

# Tat toan bo ghi nhat ky mot cho neu can.
ENABLED = True


def _safe(fn):
    try:
        return fn()
    except Exception:
        return "?"


def _post(payload: dict) -> None:
    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            LOG_URL, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass  # loi mang khong duoc lam hong app


def log(event: str, **data) -> "threading.Thread | None":
    """Gui mot su kien len server. Tra ve Thread (de join khi dong app) hoac None.

    Vd: telemetry.log("app_open", accounts_total=12)
    host + user giup biet may/nhan vien nao.
    """
    if not ENABLED or "<IP_VPS>" in LOG_URL:
        return None
    payload = {
        "service": SERVICE,
        "level": "info",
        "event": event,
        "data": {
            "host": _safe(socket.gethostname),
            "user": _safe(getpass.getuser),
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            **data,
        },
    }
    t = threading.Thread(target=_post, args=(payload,), daemon=True)
    t.start()
    return t
