"""ldauto -- tu dong hoa LDPlayer.

Import LUOI (PEP 562): nap ldauto khong keo theo adbutils/cv2 tru khi that su
dung toi Instance/Farm/flow. Nho vay cong cu chi doc DB (xem/xuat tai khoan)
chay duoc ma khong can cai dependency cua emulator.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

# ten -> module chua no
_LAZY = {
    "LDConsole": ".console", "LDConsoleError": ".console", "InstanceInfo": ".console",
    "Farm": ".farm", "Spec": ".farm",
    "FlowResult": ".flow", "Log": ".flow", "report": ".flow", "run_parallel": ".flow",
    "Instance": ".instance",
    "Account": ".accounts", "AccountStore": ".accounts",
    "random_username": ".accounts", "random_password": ".accounts",
    "ensure_warning_prefix": ".cookie", "read_roblosecurity": ".cookie",
    "verify_cookie": ".cookie",
}

__all__ = list(_LAZY)


def __getattr__(name: str):
    mod = _LAZY.get(name)
    if mod is None:
        raise AttributeError(f"module 'ldauto' has no attribute {name!r}")
    return getattr(importlib.import_module(mod, __name__), name)


def __dir__() -> list[str]:
    return sorted(__all__)


if TYPE_CHECKING:  # cho type checker / IDE thay ten that
    from .accounts import (Account, AccountStore, random_password,
                           random_username)
    from .console import InstanceInfo, LDConsole, LDConsoleError
    from .cookie import ensure_warning_prefix, read_roblosecurity, verify_cookie
    from .farm import Farm, Spec
    from .flow import FlowResult, Log, report, run_parallel
    from .instance import Instance
