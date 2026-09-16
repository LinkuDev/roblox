"""Test rieng cach hold-press tren man Security.

Cach dung:
  1. Mo LDPlayer (may ten 'roblox'), thao tac tay toi man "Hold the button".
  2. Chay script nay -> no giu nut de xem qua duoc khong.

    python examples/test_hold.py                 # roblox, (200,155), giu 8s, drift 3
    python examples/test_hold.py --x 200 --y 150 # thu toa do khac
    python examples/test_hold.py --sec 10        # giu lau hon
    python examples/test_hold.py --drift 0       # giu dung im (khong xe dich)
    python examples/test_hold.py --tap           # chi TAP 1 phat de kiem tra toa do
    python examples/test_hold.py --name roblox2  # may ao khac

Muc dich: tach rieng de dieu chinh nhanh, khong phai chay ca flow.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ldauto import Instance, LDConsole  # noqa: E402

LDCONSOLE = r"C:\LDPlayer\LDPlayer9\dnconsole.exe"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ldconsole", default=LDCONSOLE)
    ap.add_argument("--name", default="roblox", help="ten may ao LD (mac dinh roblox)")
    ap.add_argument("--x", type=int, default=200)
    ap.add_argument("--y", type=int, default=155)
    ap.add_argument("--sec", type=float, default=8.0, help="giu bao nhieu giay")
    ap.add_argument("--drift", type=int, default=3,
                    help="xe dich px trong luc giu (0 = dung im)")
    ap.add_argument("--tap", action="store_true",
                    help="chi TAP 1 phat (de kiem tra toa do co trung nut khong)")
    ap.add_argument("--countdown", type=int, default=3,
                    help="dem nguoc truoc khi bat dau (giay)")
    args = ap.parse_args()

    console = LDConsole(args.ldconsole)

    info = console.find(args.name)
    if info is None:
        print(f"[FAIL] Khong thay may ao ten {args.name!r}. Dang co:")
        for i in console.list2():
            print(f"    index={i.index} name={i.name!r} running={i.running}")
        return 1
    if not info.running:
        print(f"[FAIL] May {args.name!r} chua chay. Mo LDPlayer len truoc da.")
        return 1

    inst = Instance(console, info.index)
    print(f"Ket noi ADB {inst.serial} (index {info.index})...")
    inst.connect()

    try:
        w, h = inst.screen_resolution()
        print(f"Do phan giai may: {w}x{h}")
        if (w, h) != (400, 500):
            print(f"  * CANH BAO: toa do mac dinh (200,155) tinh cho 400x500. "
                  f"May nay {w}x{h} -> can quy doi toa do cho khop.")
    except Exception as exc:
        print(f"  (khong doc duoc do phan giai: {exc})")

    for n in range(args.countdown, 0, -1):
        print(f"  bat dau sau {n}s... (dam bao dang o man Security)")
        time.sleep(1)

    if args.tap:
        print(f"TAP tai ({args.x}, {args.y}) -- nhin nut co nhay/phan ung khong")
        inst.tap(args.x, args.y)
    else:
        print(f"HOLD tai ({args.x}, {args.y}) trong {args.sec}s, drift={args.drift}px...")
        t0 = time.time()
        inst.hold(args.x, args.y, seconds=args.sec, drift=args.drift)
        print(f"  giu xong sau {time.time() - t0:.1f}s")

    print("\n=> Nhin man hinh LD xem ket qua:")
    print("   - Nut chay thanh tien trinh / doi mau roi qua man khac  -> OK")
    print("   - Nut khong nhuc nhich                                  -> SAI TOA DO")
    print("     (bat Pointer location tren may de do X,Y that roi chay lai voi --x --y)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
