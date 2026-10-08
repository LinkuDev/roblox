#!/usr/bin/env python3
"""Click vao cua so Roblox/LDPlayer de in ra toa do tuong doi so voi cua so.

    python coords.py                  # tu tim cua so co ten "roblox" hoac "LDPlayer"
    python coords.py --name "bot0"    # tim theo ten cua so cu the
    python coords.py --list           # liet ke tat ca cua so dang mo

Nhan Ctrl+C de thoat.
"""

import argparse
import re
import subprocess
import sys
import time


def find_windows(name: str) -> list[tuple[str, str]]:
    result = subprocess.run(
        ["xdotool", "search", "--name", name],
        capture_output=True, text=True,
    )
    wids = [w.strip() for w in result.stdout.strip().split("\n") if w.strip()]
    out = []
    for wid in wids:
        title = subprocess.run(
            ["xdotool", "getwindowname", wid],
            capture_output=True, text=True,
        ).stdout.strip()
        out.append((wid, title))
    return out


def get_client_geometry(wid: str) -> dict[str, int]:
    """Dung xwininfo de lay toa do CLIENT AREA (khong tinh title bar / vien).

    Tra ve {'x': abs_x, 'y': abs_y, 'w': width, 'h': height}.
    """
    result = subprocess.run(
        ["xwininfo", "-id", wid],
        capture_output=True, text=True,
    )
    text = result.stdout
    info = {}
    for pattern, key in [
        (r"Absolute upper-left X:\s*(\d+)", "x"),
        (r"Absolute upper-left Y:\s*(\d+)", "y"),
        (r"Width:\s*(\d+)", "w"),
        (r"Height:\s*(\d+)", "h"),
    ]:
        m = re.search(pattern, text)
        if m:
            info[key] = int(m.group(1))
    return info


def list_windows():
    result = subprocess.run(
        ["xdotool", "search", "--name", ""],
        capture_output=True, text=True,
    )
    for wid in result.stdout.strip().split("\n"):
        wid = wid.strip()
        if not wid:
            continue
        title = subprocess.run(
            ["xdotool", "getwindowname", wid],
            capture_output=True, text=True,
        ).stdout.strip()
        if title:
            print(f"  {wid}  {title}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default=None,
                    help="Ten cua so can tim (mac dinh: thu roblox, LDPlayer)")
    ap.add_argument("--list", action="store_true", help="Liet ke cua so")
    args = ap.parse_args()

    if args.list:
        list_windows()
        return

    # Tim cua so
    names_to_try = [args.name] if args.name else ["roblox", "Roblox", "LDPlayer", "ldplayer"]
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
        for i, (wid, title) in enumerate(windows):
            print(f"  [{i}] {wid} - {title}")
        choice = input("Chon so: ").strip()
        wid, title = windows[int(choice)]
    else:
        wid, title = windows[0]

    geo = get_client_geometry(wid)
    cx, cy = geo["x"], geo["y"]
    cw, ch = geo["w"], geo["h"]

    print(f"\nCua so: \"{title}\" (id={wid})")
    print(f"Client area: ({cx}, {cy}), size: {cw}x{ch}")
    print(f"Click vao cua so de do toa do. Nhan Ctrl+C de thoat.\n")

    try:
        from pynput import mouse

        def on_click(x, y, button, pressed):
            if not pressed:
                return
            # Toa do tuong doi so voi client area
            rx = x - cx
            ry = y - cy
            if 0 <= rx <= cw and 0 <= ry <= ch:
                print(f"  -> ({rx}, {ry})")
            else:
                print(f"  (ngoai cua so)")

        print("Dang nghe click... (pynput)\n")
        with mouse.Listener(on_click=on_click) as listener:
            listener.join()

    except ImportError:
        print("Khong co pynput -> polling mode. pip install pynput de tot hon.\n")
        print("Di chuyen chuot vao cua so de xem toa do (realtime):\n")
        while True:
            result = subprocess.run(
                ["xdotool", "getmouselocation", "--shell"],
                capture_output=True, text=True,
            )
            info = {}
            for line in result.stdout.strip().split("\n"):
                if "=" in line:
                    k, v = line.split("=", 1)
                    info[k] = v
            mx, my = int(info["X"]), int(info["Y"])
            rx = mx - cx
            ry = my - cy
            if 0 <= rx <= cw and 0 <= ry <= ch:
                sys.stdout.write(f"\r  -> ({rx:4d}, {ry:4d})    ")
                sys.stdout.flush()
            time.sleep(0.1)


if __name__ == "__main__":
    main()
