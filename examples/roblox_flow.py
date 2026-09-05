"""Flow day du: dung 4 may ao, moi may bat VPN roi mo Roblox.

    python examples/roblox_flow.py --clone     # lan dau: clone cho du 4 may
    python examples/roblox_flow.py             # cac lan sau: chi chay flow
    python examples/roblox_flow.py --dump-ui   # xem ExpressVPN co node nao

Thao tac trong Roblox them vao ham flow(), muc 5.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ldauto import Farm, Instance, LDConsole, Log, Spec, report, run_parallel  # noqa: E402

# --------------------------------------------------------------------------
LDCONSOLE = r"C:\LDPlayer\LDPlayer9\dnconsole.exe"

SOURCE = "roblox"          # may ao goc, da cai + dang nhap san ExpressVPN
PREFIX = "bot"             # clone: bot0, bot1, bot2
CLONES = 3                 # 1 goc + 3 clone = 4 may

VPN_PKG = "com.expressvpn.vpn"
ROBLOX_PKG = "com.roblox.client"

CPU, MEMORY, CPU_LIMIT = 2, 2048, 60
STAGGER = 25               # giay giua moi may khi bat -- 4 may cung luc se nghen
RESOLUTION = None          # None = giu nguyen theo may goc

# Nhan Connect cua ExpressVPN. Script thu lan luot tu tren xuong; cai nao khop
# truoc thi bam. Chay --dump-ui de xem app that su lo ra chu gi roi sua list nay.
VPN_CONNECT_HINTS = [
    {"desc": "Connect"},
    {"text": "Connect"},
    {"text": "Tap to connect"},
    {"res_id": "connect_button"},
    {"res_id": "connectButton"},
]
# --------------------------------------------------------------------------


def connect_vpn(inst: Instance, log: Log) -> None:
    """Mo ExpressVPN va bat toggle. Moc thanh cong la interface tun, khong phai chu tren man hinh."""
    if inst.vpn_connected():
        log("VPN da len tu truoc, bo qua")
        return

    inst.start_app_adb(VPN_PKG)
    time.sleep(4)  # cho app ve xong man hinh chinh truoc khi dump UI

    # Hop thoai "Connection request" cua he thong -- chi hien lan dau tren may chua
    # tung bam OK. Clone ke thua consent tu may goc nen thuong khong gap.
    for label in ("OK", "Allow", "Dong y"):
        if inst.tap_node(text=label):
            log(f"da bam '{label}' o hop thoai VPN cua he thong")
            time.sleep(2)
            break

    nodes = inst.ui_nodes()
    for hint in VPN_CONNECT_HINTS:
        n = inst.find_node(**hint, nodes=nodes)
        if n:
            log(f"bam Connect qua {hint} tai {n['center']}")
            inst.tap(*n["center"])
            break
    else:
        # ExpressVPN dat nut Connect la mot vong tron to giua man hinh. Khong tim
        # duoc node thi bam giua -- kem chac chan, nen bao ro de con sua hint.
        log("KHONG tim thay nut Connect qua uiautomator -> bam giua man hinh")
        log("   chay lai voi --dump-ui roi sua VPN_CONNECT_HINTS cho dung")
        inst.tap_percent(50, 45)

    inst.wait_vpn(timeout=90)
    log("VPN da len (co interface tun)")


def flow(inst: Instance, log: Log) -> None:
    """Kich ban chay tren MOI may ao. Cac thread deu chay ham nay."""

    # 1. bat may ao, doi Android san sang
    log("dang bat may ao...")
    inst.start()
    log(f"san sang -> {inst.serial}")
    if CPU_LIMIT:
        inst.console.down_cpu(inst.index, CPU_LIMIT)

    # 2. VPN truoc, Roblox sau -- mo Roblox truoc thi no da bat dau noi mang
    #    bang IP that roi moi bi doi duong, de sinh loi ket noi giua chung.
    connect_vpn(inst, log)

    # 3. mo Roblox
    log(f"dang mo {ROBLOX_PKG}...")
    inst.start_app_adb(ROBLOX_PKG)

    # 4. xac nhan len foreground that su
    for _ in range(30):
        time.sleep(2)
        if inst.current_app() == ROBLOX_PKG:
            break
    else:
        raise RuntimeError(f"Roblox khong len foreground (dang o {inst.current_app()!r})")
    log("Roblox da mo")

    # 5. ------- THAO TAC TIEP THEO DAT O DAY -------
    # Roblox ve bang game engine nen uiautomator KHONG doc duoc node nao trong
    # game. Tu day tro di phai dung anh mau:
    #
    #     inst.tap_image(IMG / "play.png", timeout=60)
    #     inst.swipe_percent(50, 80, 50, 30)
    #
    # Anh mau phai chup o dung do phan giai cua may ao nay.
    log("(chua co thao tac nao sau khi mo Roblox)")


def build_instances(console: LDConsole, do_clone: bool) -> list[Instance]:
    src = console.find(SOURCE)
    if src is None:
        print(f"[FAIL] Khong co may ao {SOURCE!r}. Dang co:")
        for i in console.list2():
            print(f"    index={i.index} name={i.name!r}")
        sys.exit(1)

    if RESOLUTION:
        w, h, dpi = RESOLUTION
    else:
        w, h, dpi = src.width or 400, src.height or 500, src.dpi or 160
    print(f"Nguon: index={src.index} {src.name!r} {w}x{h}@{dpi}")

    instances = [Instance(console, src.index)]
    if do_clone:
        spec = Spec(width=w, height=h, dpi=dpi, cpu=CPU, memory=MEMORY)
        farm = Farm(console)
        for i in range(CLONES):
            name = f"{PREFIX}{i}"
            t0 = time.monotonic()
            print(f"[{name}] copy tu {SOURCE}... (vai GB, doi vai phut)")
            # Truyen index chu khong phai ten: `ldconsole copy --from` nhan index
            # chac chan, con nhan ten thi tuy phien ban.
            inst = farm.ensure(name, spec, source=src.index)
            print(f"[{name}] xong sau {time.monotonic() - t0:.0f}s -> index={inst.index}")
            instances.append(inst)
    else:
        for i in range(CLONES):
            info = console.find(f"{PREFIX}{i}")
            if info is None:
                print(f"[FAIL] Chua co may ao {PREFIX}{i!r}. Chay lai voi --clone.")
                sys.exit(1)
            instances.append(Instance(console, info.index))

    print(f"Tong {len(instances)} may ao: {[i.index for i in instances]}\n")
    return instances


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clone", action="store_true", help="clone cho du 4 may truoc khi chay")
    ap.add_argument("--dump-ui", action="store_true",
                    help="mo ExpressVPN tren may goc va in cay giao dien roi thoat")
    ap.add_argument("--ldconsole", default=LDCONSOLE)
    ap.add_argument("--stagger", type=float, default=STAGGER)
    args = ap.parse_args()

    console = LDConsole(args.ldconsole)

    if args.dump_ui:
        src = console.find(SOURCE)
        inst = Instance(console, src.index)
        inst.start()
        inst.start_app_adb(VPN_PKG)
        time.sleep(5)
        print(f"\nNode co the bam duoc trong {VPN_PKG}:\n")
        for n in inst.ui_nodes():
            if n["clickable"] or n["text"] or n["desc"]:
                print(f"  text={n['text']!r:30} desc={n['desc']!r:25} "
                      f"id={n['id'].split('/')[-1]!r:22} click={n['clickable']} @{n['center']}")
        print("\n-> Chep dong dung voi nut Connect vao VPN_CONNECT_HINTS.")
        return 0

    instances = build_instances(console, args.clone)
    results = run_parallel(instances, flow, stagger=args.stagger)
    return report(results)


if __name__ == "__main__":
    sys.exit(main())
