"""Flow day du: dung 4 may ao, moi may bat VPN roi mo Roblox.

    python examples/roblox_flow.py --clone     # lan dau: clone cho du 4 may
    python examples/roblox_flow.py             # cac lan sau: chi chay flow
    python examples/roblox_flow.py --dump-ui   # xem ExpressVPN co node nao

Thao tac trong Roblox them vao ham flow(), muc 5.
"""

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ldauto import Farm, Instance, LDConsole, Log, Spec, report, run_parallel  # noqa: E402
from ldauto import window  # noqa: E402

# --------------------------------------------------------------------------
LDCONSOLE = r"C:\LDPlayer\LDPlayer9\dnconsole.exe"

SOURCE = "roblox"          # may ao goc, da cai + dang nhap san ExpressVPN
PREFIX = "bot"             # clone: bot0, bot1, bot2
CLONES = 3                 # 1 goc + 3 clone = 4 may

VPN_PKG = "com.expressvpn.vpn"
ROBLOX_PKG = "com.roblox.client"

CPU, MEMORY, CPU_LIMIT = 2, 2048, 60
STAGGER = 12               # giay giua moi may khi bat -- 4 may cung luc se nghen
AUTOCONNECT_WAIT = 12      # giay doi ExpressVPN tu noi lai truoc khi can thiep
RESOLUTION = None          # None = giu nguyen theo may goc

# Nut Connect cua ExpressVPN, lay tu --dump-ui. Day la TOGGLE: bam khi dang bat
# thi no NGAT vpn -- vi vay connect_vpn() kiem tra trang thai truoc, khong bam mu.
VPN_CONNECT_HINTS = [
    {"res_id": "vpn_connect_button"},
]
VPN_STATUS_ID = "vpn_connection_status_text"   # 'Protected | 00:04:20' khi dang bat

# Doc trang thai tu chinh dong chu do. Dung \b: 'Unprotected' chua 'protected',
# con 'Not connected' / 'Disconnected' thi chua 'connected' -- so bang `in` la
# nham ca hai chieu.
VPN_ON_RE = re.compile(r"\bprotected\b", re.I)
VPN_OFF_RE = re.compile(r"\bnot\b|\bdisconnect", re.I)


def status_says_on(text: str) -> bool:
    return bool(VPN_ON_RE.search(text)) and not VPN_OFF_RE.search(text)


# Index nao can xoa du lieu Roblox truoc khi mo. Dat trong main(): clone luon
# duoc xoa (khong thi 4 may dung chung mot phien dang nhap), may goc thi khong
# -- do la may ban dung tay, xoa la mat du lieu that.
CLEAR_ROBLOX_ON: set[int] = set()
REUSE = False                # --reuse: dung tiep may ao dang chay

# index -> o thu may tren luoi. Toa do khong dat cung o day ma tinh luc chay,
# tu be rong that cua cua so -- xem window.slot_pos().
WINDOW_SLOT: dict[int, int] = {}
WINDOW_COLS = 4              # 4 may nam ngang mot hang
WINDOW_ORIGIN = (0, 0)       # goc tren trai man hinh
WINDOW_GAP = (8, 8)          # khe ho giua hai cua so
CHROME = (40, 90)            # vien + tieu de + cot cong cu, chi dung khi do hut
# --------------------------------------------------------------------------


def connect_vpn(inst: Instance, log: Log) -> None:
    """Bat VPN neu chua bat.

    Moc that su la interface tun co dia chi IP, khong phai chu tren man hinh:
    app bao 'Connected' ma khong co tun nghia la duong ham chua dung duoc.
    """
    # ExpressVPN tu ket noi lai khi may ao khoi dong (thua tu may goc), nhung mat
    # vai chuc giay. Kiem tra mot lan ngay sau boot la qua som: tun chua len,
    # script tuong chua bat roi bam nut -- ma do la TOGGLE, tuc ngat mat cai
    # dang tu noi. Doi han ra truoc khi can thiep.
    for _ in range(AUTOCONNECT_WAIT // 3):
        if inst.vpn_connected():
            log("VPN tu len sau khi boot -- khong dung toi nut Connect")
            return
        time.sleep(3)

    inst.start_app_adb(VPN_PKG)
    time.sleep(4)  # cho app ve xong man hinh chinh truoc khi dump UI

    # Hop thoai "Connection request" cua he thong -- chi hien tren may chua tung
    # bam OK. Clone ke thua consent tu may goc nen thuong khong gap.
    for label in ("OK", "Allow", "Dong y"):
        if inst.tap_node(text=label):
            log(f"da bam '{label}' o hop thoai VPN cua he thong")
            time.sleep(2)
            break

    nodes = inst.ui_nodes()
    status = inst.find_node(res_id=VPN_STATUS_ID, nodes=nodes)
    txt = status["text"] if status else ""
    if status:
        log(f"trang thai app: {txt!r}")

    if status_says_on(txt):
        # App da bat roi, chi la tun chua kip len. Bam vao day la NGAT.
        log("app bao dang ket noi -- khong bam nut, chi doi tun")
    else:
        for hint in VPN_CONNECT_HINTS:
            n = inst.find_node(**hint, nodes=nodes)
            if n:
                log(f"bam Connect ({hint}) tai {n['center']}")
                inst.tap(*n["center"])
                break
        else:
            # Nut nguon nam giua man hinh, hoi cao hon tam. Kem chac chan hon han
            # res_id nen phai bao ro la dang doan.
            log("KHONG thay nut Connect qua uiautomator -> bam giua man hinh")
            log("   chay lai voi --dump-ui roi sua VPN_CONNECT_HINTS cho dung")
            inst.tap_percent(50, 39)

    try:
        inst.wait_vpn(timeout=120)
    except TimeoutError:
        # Doi ma khong len: hoac cu bam vua roi ngat nham, hoac app that su chua
        # noi duoc. Bam mot lan nua roi doi tiep -- chi mot lan, khong lap vo han.
        log("tun chua len sau 120s -> bam Connect them mot lan roi doi tiep")
        if not inst.tap_node(**VPN_CONNECT_HINTS[0]):
            inst.tap_percent(50, 39)
        inst.wait_vpn(timeout=120)
    log("VPN da len (tun co IP)")


def flow(inst: Instance, log: Log) -> None:
    """Kich ban chay tren MOI may ao. Cac thread deu chay ham nay."""

    # 1. bat may ao, doi Android san sang.
    #    restart() thay vi start(): dung tiep may ao dang chay se mang theo moi
    #    thu con sot lai cua phien truoc -- app mo do dang, VPN nua chung,
    #    dialog chua tat. Bat lai tu dau re hon la doan xem con gi sot.
    log("dang bat may ao...")
    inst.start() if REUSE else inst.restart(log)
    log(f"san sang -> {inst.serial}")

    # 1b. keo cua so ve o cua no. Lay handle tu list2 chu khong do theo tieu de:
    #     tieu de cua so LDPlayer la ten app dang mo ('Roblox'), khong phai ten
    #     may ao. Phai doc SAU khi may ao bat xong -- luc tat handle bang 0.
    slot = WINDOW_SLOT.get(inst.index)
    if slot is not None:
        info = inst.console.find(inst.index)
        hwnd = info.top_window_handle if info else 0
        pos = window.slot_pos(hwnd, slot, cols=WINDOW_COLS,
                              origin=WINDOW_ORIGIN, gap=WINDOW_GAP)
        if pos is None and info and info.width:
            # Do khong duoc thi suy tu do phan giai may ao, cong CHROME cho phan
            # khung: vien cua so, thanh tieu de va cot cong cu ben phai cua
            # LDPlayer deu nam ngoai vung 400x500 do.
            w, h = info.width + CHROME[0], (info.height or 500) + CHROME[1]
            pos = (WINDOW_ORIGIN[0] + (slot % WINDOW_COLS) * (w + WINDOW_GAP[0]),
                   WINDOW_ORIGIN[1] + (slot // WINDOW_COLS) * (h + WINDOW_GAP[1]))
            log(f"khong do duoc cua so -> suy tu {info.width}x{info.height} + chrome")
        if pos and window.place_hwnd(hwnd, *pos):
            log(f"cua so -> o {slot} tai {pos} (hwnd={hwnd})")
        else:
            log(f"khong keo duoc cua so, hwnd={hwnd} -- bo qua")

    # 2. VPN truoc, Roblox sau -- mo Roblox truoc thi no da bat dau noi mang
    #    bang IP that roi moi bi doi duong, de sinh loi ket noi giua chung.
    connect_vpn(inst, log)

    # 3. mo Roblox
    if inst.index in CLEAR_ROBLOX_ON:
        log(f"xoa du lieu {ROBLOX_PKG} (ve nhu vua cai)")
        inst.clear_app(ROBLOX_PKG)
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
    ap.add_argument("--clear-roblox", action="store_true",
                    help="xoa du lieu Roblox tren MOI may, ke ca may goc")
    ap.add_argument("--keep-roblox-data", action="store_true",
                    help="khong xoa gi, ke ca tren clone moi tao")
    ap.add_argument("--no-arrange", action="store_true",
                    help="khong keo cua so, de LDPlayer tu dat")
    ap.add_argument("--list-windows", action="store_true",
                    help="in moi cua so dang mo roi thoat (de tim dung tieu de)")
    ap.add_argument("--reuse", action="store_true",
                    help="dung tiep may ao dang chay thay vi tat roi bat lai")
    args = ap.parse_args()

    global REUSE
    REUSE = args.reuse

    if args.list_windows:
        print("Handle ldconsole bao (list2):")
        for i in console.list2():
            print(f"  index={i.index:<6} name={i.name!r:12} top_window={i.top_window_handle} "
                  f"bind_window={i.bind_window_handle}")
        print("\nCua so Windows dang mo:")
        for hwnd, title, cls in window.list_windows():
            print(f"  hwnd={hwnd:<10} class={cls:<28} title={title!r}")
        return 0

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

    if not args.no_arrange:
        for slot, inst in enumerate(instances):
            WINDOW_SLOT[inst.index] = slot
        print(f"Xep cua so: {WINDOW_COLS} cot, moi may mot o "
              f"(be rong do luc chay, khong dat cung)")

    if args.keep_roblox_data:
        pass
    elif args.clear_roblox:
        CLEAR_ROBLOX_ON.update(i.index for i in instances)
        print(f"Se xoa du lieu Roblox tren TAT CA: {sorted(CLEAR_ROBLOX_ON)}")
    elif args.clone:
        # instances[0] la may goc -- khong dung toi. Chi clone vua tao moi xoa.
        CLEAR_ROBLOX_ON.update(i.index for i in instances[1:])
        print(f"Se xoa du lieu Roblox tren clone moi: {sorted(CLEAR_ROBLOX_ON)}")
    print()

    results = run_parallel(instances, flow, stagger=args.stagger)
    return report(results)


if __name__ == "__main__":
    sys.exit(main())
