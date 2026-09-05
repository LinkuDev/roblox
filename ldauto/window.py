"""Xep cua so LDPlayer ra cac vi tri khac nhau tren man hinh Windows.

Dung ctypes goi thang user32 -- khong can pywin32. Chi chay tren Windows;
tren he khac moi ham tra ve gia tri rong thay vi no.

`ldconsole sortWnd` cung xep duoc, nhung theo luoi cua LDPlayer chu khong cho
chon toa do. Module nay de tu dat tung cua so vao dung cho.
"""

from __future__ import annotations

import sys

_WIN = sys.platform == "win32"

if _WIN:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _EnumWindowsProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
    )
    SWP_NOZORDER = 0x0004
    SWP_NOSIZE = 0x0001
    SW_RESTORE = 9


def list_windows() -> list[tuple[int, str, str]]:
    """Moi cua so top-level dang hien: (hwnd, tieu de, ten lop)."""
    if not _WIN:
        return []
    out: list[tuple[int, str, str]] = []

    def cb(hwnd, _):
        if not _user32.IsWindowVisible(hwnd):
            return True
        n = _user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            _user32.GetWindowTextW(hwnd, buf, n + 1)
            cls = ctypes.create_unicode_buffer(256)
            _user32.GetClassNameW(hwnd, cls, 256)
            out.append((hwnd, buf.value, cls.value))
        return True

    _user32.EnumWindows(_EnumWindowsProc(cb), 0)
    return out


def find(title: str) -> int | None:
    """hwnd cua cua so co tieu de khop. Uu tien khop chinh xac roi moi khop mot phan.

    Khop chinh xac truoc la co y: ten may ao 'bot1' nam trong 'bot10', va cua so
    Roblox trong may ao cung co the chua chu tuong tu.
    """
    wins = list_windows()
    for hwnd, t, _ in wins:
        if t == title:
            return hwnd
    for hwnd, t, _ in wins:
        if title.lower() in t.lower():
            return hwnd
    return None


def place_hwnd(
    hwnd: int,
    x: int,
    y: int,
    width: int | None = None,
    height: int | None = None,
) -> bool:
    """Dat cua so theo handle. Cach chac chan nhat: khoi doan tieu de.

    `ldconsole list2` tra ve san handle o cot 3 (top_window_handle), nen lay
    thang tu do. Handle bang 0 nghia la may ao chua bat.
    """
    if not _WIN or not hwnd:
        return False
    if not _user32.IsWindow(hwnd):
        return False
    # Cua so dang thu nho thi SetWindowPos khong co tac dung nhin thay duoc.
    _user32.ShowWindow(hwnd, SW_RESTORE)
    flags = SWP_NOZORDER | (SWP_NOSIZE if width is None or height is None else 0)
    _user32.SetWindowPos(hwnd, 0, int(x), int(y),
                         int(width or 0), int(height or 0), flags)
    return True


def place(
    title: str,
    x: int,
    y: int,
    width: int | None = None,
    height: int | None = None,
) -> bool:
    """Dat cua so tim theo tieu de. Kem chac hon place_hwnd -- tieu de cua so
    LDPlayer la ten APP dang mo, khong phai ten may ao."""
    hwnd = find(title)
    return place_hwnd(hwnd, x, y, width, height) if hwnd else False


def grid(
    count: int,
    cols: int = 2,
    origin: tuple[int, int] = (0, 0),
    cell: tuple[int, int] = (420, 620),
) -> list[tuple[int, int]]:
    """Toa do cho `count` cua so xep theo luoi.

    cell la buoc nhay, khong phai kich thuoc cua so -- de rong hon cua so mot
    chut cho khoi de len nhau.
    """
    x0, y0 = origin
    dx, dy = cell
    return [(x0 + (i % cols) * dx, y0 + (i // cols) * dy) for i in range(count)]
