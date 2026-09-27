"""Xem widget tree cua man "All Locations" trong ExpressVPN.

Dung de kiem chung truoc khi tin vao bo loc doan ten nuoc: mo tay ExpressVPN
toi dung man danh sach nuoc, roi chay file nay de nhin app that su lo ra cai gi.

    # chi dump man hinh dang hien
    python examples/dump_vpn_list.py --name roblox

    # dump + cuon thu 5 nac, xem gom duoc nhung nuoc nao
    python examples/dump_vpn_list.py --name roblox --scrolls 5

    # chay het nhu flow that lam (cuon toi cuoi danh sach)
    python examples/dump_vpn_list.py --name roblox --collect
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ldauto import Instance, LDConsole, Log  # noqa: E402
import roblox_flow as rf  # noqa: E402


def dump_screen(inst: Instance, title: str) -> list[dict]:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")
    try:
        nodes = inst.ui_nodes()
    except Exception as exc:
        print(f"  [!] doc UI hong: {type(exc).__name__}: {exc}")
        return []

    rows = dict(rf._country_rows(nodes))
    shown = [n for n in nodes if n["text"].strip() or n["desc"].strip() or n["clickable"]]
    print(f"{len(nodes)} node, {len(shown)} co chu hoac bam duoc\n")
    print(f"  {'NUOC?':6} {'text':28} {'id':26} {'class':22} clk  center")
    print(f"  {'-' * 6} {'-' * 28} {'-' * 26} {'-' * 22} ---  ------")
    for n in shown:
        ok = n["text"].strip() in rows
        print(f"  {'[x]' if ok else '[ ]':6} "
              f"{n['text'].strip()[:28]:28} "
              f"{n['id'].split('/')[-1][:26]:26} "
              f"{n['class'].split('.')[-1][:22]:22} "
              f"{'Y' if n['clickable'] else '.':3}  {n['center']}")

    print(f"\n  -> ghep duoc {len(rows)} hang nuoc:")
    for name, pos in rows.items():
        print(f"       {name:28} bam tai {pos}")
    return nodes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ldconsole", default=rf.LDCONSOLE)
    ap.add_argument("--name", help="ten may ao (vd roblox)")
    ap.add_argument("--index", type=int, help="hoac index may ao")
    ap.add_argument("--port", type=int, help="cong ADB neu quy uoc 5555+idx*2 sai")
    ap.add_argument("--scrolls", type=int, default=0,
                    help="dump man hien tai roi cuon N nac, dump lai moi nac")
    ap.add_argument("--collect", action="store_true",
                    help="chay dung ham gom cua flow (_collect_countries)")
    ap.add_argument("--max-scrolls", type=int, default=rf.VPN_LIST_MAX_SCROLLS,
                    help="tran so nac cuon khi --collect (mac dinh %(default)s, "
                         "moi nac ~3s)")
    ap.add_argument("--top", action="store_true",
                    help="cuon ve dau danh sach truoc khi lam gi")
    args = ap.parse_args()

    console = LDConsole(args.ldconsole)
    if args.index is not None:
        idx = args.index
    elif args.name:
        info = console.find(args.name)
        if info is None:
            print(f"[FAIL] khong co may ao {args.name!r}. Dang co:")
            for i in console.list2():
                print(f"    index={i.index} name={i.name!r}")
            return 1
        idx = info.index
    else:
        ap.error("can --name hoac --index")

    inst = Instance(console, idx, adb_port=args.port)
    inst.connect()
    print(f"noi duoc {inst.serial} (index={idx})")
    print(f"man hinh: {inst.screen_resolution()}")
    print(f"app dang o truoc: {inst.current_app()!r}")

    if args.top:
        print("cuon ve dau danh sach...")
        rf._scroll_to_top(inst)

    if args.collect:
        log = Log("dump")
        names = rf._collect_countries(inst, log, max_scrolls=args.max_scrolls)
        print(f"\n{'=' * 78}\nGOM DUOC {len(names)} NUOC\n{'=' * 78}")
        for i, n in enumerate(names, 1):
            print(f"  {i:3}. {n:28} (thay o nac cuon {rf._country_step.get(n)})")
        return 0

    dump_screen(inst, "MAN HINH HIEN TAI")
    for k in range(args.scrolls):
        rf._scroll_list(inst)
        dump_screen(inst, f"SAU KHI CUON {k + 1} NAC "
                          f"(anchor={rf.VPN_LIST_ANCHOR}, dy={rf.VPN_LIST_SCROLL_DY})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
