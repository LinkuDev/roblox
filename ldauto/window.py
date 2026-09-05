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


def rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """(x, y, rong, cao) cua cua so, hoac None neu handle khong dung."""
    if not _WIN or not hwnd or not _user32.IsWindow(hwnd):
        return None
    r = wintypes.RECT()
    if not _user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def slot_pos(
    hwnd: int,
    slot: int,
    cols: int = 4,
    origin: tuple[int, int] = (0, 0),
    gap: tuple[int, int] = (8, 8),
) -> tuple[int, int] | None:
    """Vi tri cho o thu `slot`, tinh tu BE RONG THAT cua chinh cua so do.

    Dat buoc nhay bang tay thi luon doan sai: be rong cua so LDPlayer khong
    bang do phan giai may ao -- con vien, thanh tieu de va cot cong cu ben
    phai. Do roi tinh thi khong bao gio chong nhau.

    Moi may ao cung do phan giai nen moi thread tu do cua so cua minh deu ra
    cung mot con so -- khong can dong bo giua cac thread.
    """
    r = rect(hwnd)
    if r is None:
        return None
    _, _, w, h = r
    x0, y0 = origin
    gx, gy = gap
    return x0 + (slot % cols) * (w + gx), y0 + (slot // cols) * (h + gy)


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
    """Dat cua so tim theo tieu de.

    Tieu de cua so LDPlayer chinh la ten may ao ('bot0', 'roblox'...), nen cach
    nay chay duoc. Van nen dung place_hwnd khi co handle: khop chuoi con mo ho
    ('bot1' nam trong 'bot10'), va may ao dang tat thi khong co cua so nao de
    khop ca -- trong khi list2 dua thang handle, khong phai doan gi.
    """
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
