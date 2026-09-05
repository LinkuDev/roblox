"""Mo mot app da cai san trong may ao LDPlayer.

Liet ke app de tim package name:
    python examples/open_app.py --index 1 --list
    python examples/open_app.py --index 1 --find vpn

Mo app:
    python examples/open_app.py --index 1 com.example.vpn

App VPN can them buoc cho phep -- xem --grant-vpn o duoi.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ldauto import Instance, LDConsole  # noqa: E402

LDCONSOLE = r"C:\LDPlayer\LDPlayer9\dnconsole.exe"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package", nargs="?", help="package name can mo")
    ap.add_argument("--index", type=int, default=0, help="index may ao (mac dinh 0)")
    ap.add_argument("--port", type=int, default=None,
                    help="cong ADB, neu quy uoc 5555+index*2 doan sai")
    ap.add_argument("--ldconsole", default=LDCONSOLE)
    ap.add_argument("--list", action="store_true", help="liet ke app da cai (tru app he thong)")
    ap.add_argument("--find", metavar="TU_KHOA", help="tim package theo tu khoa")
    ap.add_argument("--launch", action="store_true", help="bat may ao truoc neu chua chay")
    ap.add_argument("--grant-vpn", action="store_true",
                    help="cho phep app dung VPN san (CAN ROOT)")
    ap.add_argument("--stop", action="store_true", help="tat app thay vi mo")
    args = ap.parse_args()

    console = LDConsole(args.ldconsole)
    inst = Instance(console, args.index, adb_port=args.port)

    if args.launch:
        print(f"Bat may ao index={args.index}, doi boot...")
        inst.start()
    else:
        inst.connect()
    print(f"Da noi: {inst.serial}\n")

    if args.list or args.find:
        pkgs = inst.find_package(args.find) if args.find else inst.list_packages()
        if not pkgs:
            print("Khong tim thay package nao khop.")
            return 1
        for p in pkgs:
            print(f"  {p}")
        print(f"\n{len(pkgs)} package.")
        return 0

    if not args.package:
        ap.error("thieu package name (hoac dung --list / --find de tim)")

    if args.stop:
        inst.stop_app_adb(args.package)
        print(f"Da tat {args.package}")
        return 0

    if args.grant_vpn:
        ok = inst.grant_vpn(args.package)
        print("Da cho phep VPN." if ok
              else "Khong cho phep duoc (thieu root?) -- se phai bam OK bang tay.")

    print(f"Dang mo {args.package}...")
    inst.start_app_adb(args.package)

    # Doi app len foreground roi xac nhan, thay vi tin la lenh chay xong = app da mo.
    for _ in range(10):
        time.sleep(1)
        if inst.current_app() == args.package:
            print(f"[ OK ] {args.package} dang o foreground")
            return 0

    cur = inst.current_app()
    if inst.is_app_running(args.package):
        print(f"[WARN] {args.package} dang chay nhung foreground la {cur!r}.")
        print("       App VPN thuong bi hop thoai 'Connection request' cua he thong che.")
        print("       Bam OK bang tay mot lan, hoac chay lai voi --grant-vpn (can root).")
        return 0

    print(f"[FAIL] {args.package} khong chay. Foreground hien tai: {cur!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
