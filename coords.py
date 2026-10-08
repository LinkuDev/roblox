#!/usr/bin/env python3
"""Click vao cua so Roblox/LDPlayer de in ra toa do tuong doi so voi cua so.

    python coords.py                  # tu tim cua so co ten "roblox" hoac "LDPlayer"
    python coords.py --name "bot0"    # tim theo ten cua so cu the
    python coords.py --list           # liet ke tat ca cua so dang mo

Nhan Ctrl+C de thoat.
"""

import argparse
import ctypes
import ctypes.wintypes as wt
import sys

user32 = ctypes.windll.user32

# --- Win32 helpers --------------------------------------------------------

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)


def _enum_windows() -> list[tuple[int, str]]:
    """Tra ve [(hwnd, title), ...] cho tat ca cua so dang thay."""
    results: list[tuple[int, str]] = []
    buf = ctypes.create_unicode_buffer(512)

    @WNDENUMPROC
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            user32.GetWindowTextW(hwnd, buf, 512)
            title = buf.value
            if title:
                results.append((hwnd, title))
        return True

    user32.EnumWindows(cb, 0)
    return results


def find_windows(name: str) -> list[tuple[int, str]]:
    name_lower = name.lower()
    return [(h, t) for h, t in _enum_windows() if name_lower in t.lower()]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long), ("top", ctypes.c_long),
        ("right", ctypes.c_long), ("bottom", ctypes.c_long),
    ]


def get_client_origin(hwnd: int) -> tuple[int, int, int, int]:
    """Tra ve (client_x, client_y, client_w, client_h) tren man hinh."""
    pt = POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    rc = RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rc))
    return pt.x, pt.y, rc.right - rc.left, rc.bottom - rc.top


# --- Main -----------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default=None,
                    help="Ten cua so can tim (mac dinh: thu roblox, LDPlayer)")
    ap.add_argument("--list", action="store_true", help="Liet ke cua so")
    ap.add_argument("--tw", type=int, default=400, help="Target width (mac dinh 400)")
    ap.add_argument("--th", type=int, default=500, help="Target height (mac dinh 500)")
    args = ap.parse_args()

    if args.list:
        for hwnd, title in _enum_windows():
            print(f"  {hwnd:#010x}  {title}")
        return

    # Tim cua so
    names_to_try = [args.name] if args.name else ["roblox", "LDPlayer"]
    windows = []
    for n in names_to_try:
        windows = find_windows(n)
        if windows:
            break

    if not windows:
        print("Khong tim thay cua so nao! Thu: python coords.py --list")
        sys.exit(1)

    if len(windows) > 1:
        print("Tim thay nhieu cua so:")
        for i, (hwnd, title) in enumerate(windows):
            print(f"  [{i}] {hwnd:#010x} - {title}")
        choice = input("Chon so: ").strip()
        hwnd, title = windows[int(choice)]
    else:
        hwnd, title = windows[0]

    cx, cy, cw, ch = get_client_origin(hwnd)
    tw, th = args.tw, args.th
    print(f"\nCua so: \"{title}\"")
    print(f"Client area: origin=({cx}, {cy}), size={cw}x{ch}")
    print(f"Tyle quy doi ve {tw}x{th}: scale_x={tw/cw:.4f}, scale_y={th/ch:.4f}")
    print(f"Click vao cua so de do toa do. Nhan Ctrl+C de thoat.\n")

    try:
        from pynput import mouse

        def on_click(x, y, button, pressed):
            if not pressed:
                return
            rx = x - cx
            ry = y - cy
            if 0 <= rx <= cw and 0 <= ry <= ch:
                sx = round(rx * tw / cw)
                sy = round(ry * th / ch)
                print(f"  Window client: ({rx}, {ry})  =>  Quy doi {tw}x{th}: ({sx}, {sy})")
            else:
                print(f"  (ngoai cua so: screen {x}, {y})")

        print("Dang nghe click chuot...\n")
        with mouse.Listener(on_click=on_click) as listener:
            listener.join()

    except ImportError:
        print("Chua cai pynput. Hay chay: pip install pynput")
        sys.exit(1)


if __name__ == "__main__":
    main()
