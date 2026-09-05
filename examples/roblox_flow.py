"""Flow day du: dung 4 may ao, moi may bat VPN roi mo Roblox.

    python examples/roblox_flow.py --clone     # lan dau: clone cho du 4 may
    python examples/roblox_flow.py             # cac lan sau: chi chay flow
    python examples/roblox_flow.py --dump-ui   # xem ExpressVPN co node nao

Thao tac trong Roblox them vao ham flow(), muc 5.
"""

import argparse
import random
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ldauto import (AccountStore, Farm, Instance, LDConsole, Log, Spec,  # noqa: E402
                    ensure_warning_prefix, report, run_parallel)
from ldauto import window  # noqa: E402

# --------------------------------------------------------------------------
LDCONSOLE = r"C:\LDPlayer\LDPlayer9\dnconsole.exe"

SOURCE = "roblox"          # may ao goc, da cai + dang nhap san ExpressVPN
PREFIX = "bot"             # clone: bot0, bot1, bot2
CLONES = 3                 # 1 goc + 3 clone = 4 may

VPN_PKG = "com.expressvpn.vpn"
ROBLOX_PKG = "com.roblox.client"

CPU, MEMORY, CPU_LIMIT = 2, 2048, 60
STAGGER = 5                # giay giua moi may khi bat -- 4 may cung luc se nghen
AUTOCONNECT_WAIT = 30      # giay doi ExpressVPN tu noi lai truoc khi can thiep
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


# Index nao can xoa du lieu Roblox truoc khi mo. Mac dinh la TAT CA: clone thua
# nguyen phien dang nhap cua may goc, khong xoa thi ca 4 may dung chung mot tai
# khoan. --clear-clones de chua may goc ra, --keep-roblox-data de khong xoa gi.
CLEAR_ROBLOX_ON: set[int] = set()
REUSE = False                # --reuse: dung tiep may ao dang chay

# index -> o thu may tren luoi. Toa do khong dat cung o day ma tinh luc chay,
# tu be rong that cua cua so -- xem window.slot_pos().
WINDOW_SLOT: dict[int, int] = {}
WINDOW_COLS = 4              # 4 may nam ngang mot hang
WINDOW_ORIGIN = (0, 0)       # goc tren trai man hinh
WINDOW_GAP = (8, 8)          # khe ho giua hai cua so
CHROME = (40, 90)            # vien + tieu de + cot cong cu, chi dung khi do hut

# --- Man xac minh tuoi sau khi Roblox mo ---------------------------------
# Toa do pixel, dung cho man hinh 400x500. Doi do phan giai la phai do lai het.
ROBLOX_SETTLE = 15           # giay cho Roblox ve xong truoc khi bam
CONTINUE_BTN = (201, 322)    # nut Continue cua "Free item with an age check"
AFTER_CONTINUE = 5           # giay cho banh xe chon ngay hien ra

WHEELS = {                   # ba banh xe chon ngay sinh
    "thang": (107, 244),
    "ngay":  (217, 244),
    "nam":   (313, 244),
}
# Pixel moi nac, co dau: duong = ngon tay di XUONG. Thang va ngay nguoc chieu
# nam -- khong suy ra duoc tu ly thuyet, phai chay roi nhin.
SCROLL_DY = {
    "thang": -60,
    "ngay":  -60,
    "nam":    60,
}
SCROLL_PAUSE = 0.35          # giay nghi giua hai cu vuot
SCROLLS = {                  # so nac ngau nhien cho tung banh xe
    "thang": (1, 11),
    "ngay":  (1, 11),
    "nam":   (15, 20),
}
AFTER_WHEELS = 4             # giay cho sau khi cuon xong
SUBMIT_BTN = (197, 394)      # nut xac nhan duoi man chon ngay sinh
# Cho man dang ky ve XONG sau khi xac nhan ngay sinh. Truoc day khong co buoc
# cho nao o day: bam xac nhan xong la bam ngay o username, trong khi man hinh
# con dang chuyen -> cu bam roi vao khoang khong.
AFTER_SUBMIT = 12

# --- Man dang ky sau khi qua xac minh tuoi -------------------------------
# Cung he toa do 400x500 nhu tren.
STEP_PAUSE = 3               # giay giua moi thao tac
USERNAME_FIELD = (201, 266)
GENDER_FEMALE = (113, 290)   # icon ben trai
GENDER_MALE = (288, 290)     # icon ben phai
SIGNUP_CONTINUE = (200, 381)

# --- Man "Create Account" / tao mat khau ---------------------------------
# Sau khi bam Continue, Roblox mat mot luc moi ve xong man nay.
PASSWORD_WAIT = 18
# Man nay tu focus san vao o mat khau -> go thang, khong can bam truoc.
# Nut Done. Toa do UOC LUONG tu anh chup, chua do tren may that -- xem chu
# thich trong flow(). Nut cao ~40px nen lech 10-15px van trung.
DONE_BTN = (200, 370)

# Nhan chung cho MOI moc cho ben duoi (--slow). May yeu hoac chay nhieu may ao
# thi moi thu deu cham di theo cung mot ty le, khong can sua tung hang so.
SLOW = 1.0


def pause(seconds: float, log: Log | None = None, why: str = "") -> None:
    """time.sleep co nhan he so SLOW, va tinh luon ca Ctrl+C."""
    t = seconds * SLOW
    if log and why:
        log(f"cho {t:.0f}s {why}")
    STOP.wait(t)


# --- Vong lap -------------------------------------------------------------
ROUNDS = 0                   # 0 = chay khong gioi han, Ctrl+C de dung
ROUND_PAUSE = 5              # giay cho sau khi bam Done, truoc khi tat may ao
MAX_FAILS = 3                # so vong hong LIEN TIEP truoc khi bo may ao do
# Bat lai 4 may ao cung luc lam nghen dia y het luc dau -- rai ngau nhien ra.
RESTART_JITTER = 10

# Dat khi nguoi dung Ctrl+C. Thread dang chay se xong vong hien tai roi dung,
# khong cat ngang giua chung de khoi bo lai may ao dang bat.
STOP = threading.Event()

# --- Lay cookie cuoi flow ------------------------------------------------
# Cho Roblox login xong han sau khi bam Done -> cookie moi duoc ghi vao DB
# cua WebView. Lay som qua thi chua co gi.
COOKIE_WAIT = 12
VERIFY_COOKIE = True         # goi API Roblox xac nhan cookie song + dung acc

DB_PATH = "accounts.db"
STORE: AccountStore | None = None   # tao o main(), moi thread dung chung
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
    # Poll re hon HAN so voi mo app: mot lenh `ip addr` moi 2 giay, doi lai
    # bo qua duoc ca start_app + uiautomator dump. Vong nay thoat NGAY khi tun
    # len, nen cho lau khong ton gi neu VPN len som.
    deadline = time.monotonic() + AUTOCONNECT_WAIT
    while time.monotonic() < deadline:
        if inst.vpn_connected():
            log("VPN tu len sau khi boot -- khong dung toi nut Connect")
            return
        time.sleep(2)

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


def one_round(inst: Instance, log: Log) -> str:
    """Mot vong: bat may ao -> VPN -> Roblox -> tao xong mot tai khoan.

    Tra ve username vua tao, de nguoi goi ghi lai ket qua.
    """

    t0 = [time.monotonic()]

    def lap(what: str) -> None:
        """In thoi gian tung chang -- khong do thi khong biet cat cho nao."""
        now = time.monotonic()
        log(f"{what} ({now - t0[0]:.0f}s)")
        t0[0] = now

    # 1. bat may ao, doi Android san sang. May ao dang chay da duoc tat dong
    #    loat o main() truoc khi vao day, nen cho nay chi con viec bat.
    log("dang bat may ao...")
    inst.start()
    lap(f"san sang -> {inst.serial}")

    # 1b. keo cua so ve o cua no. Dung handle tu list2 chu khong do theo tieu de:
    #     tieu de DUNG la ten may ao, nhung khop chuoi con mo ho ('bot1' nam
    #     trong 'bot10'). list2 dua thang handle nen khong phai doan.
    #     Phai doc SAU khi may ao bat xong -- luc tat handle bang 0.
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
    lap("VPN xong")

    # 3. mo Roblox
    if inst.index in CLEAR_ROBLOX_ON:
        inst.clear_app(ROBLOX_PKG)
        lap(f"da xoa du lieu {ROBLOX_PKG}")
    log(f"dang mo {ROBLOX_PKG}...")
    inst.start_app_adb(ROBLOX_PKG)

    # 4. xac nhan len foreground that su
    for _ in range(30):
        if inst.current_app() == ROBLOX_PKG:
            break
        time.sleep(2)
    else:
        raise RuntimeError(f"Roblox khong len foreground (dang o {inst.current_app()!r})")
    lap("Roblox da mo")

    # 5. Man xac minh tuoi.
    #    Bam theo toa do pixel chu khong qua uiautomator: Roblox ve bang engine
    #    rieng nen khong lo ra node nao de tim. Doi lai, toa do chi dung o dung
    #    do phan giai da do -- ca 4 may deu 400x500 nen dung chung duoc.
    pause(ROBLOX_SETTLE, log, "cho Roblox ve xong")

    log(f"bam Continue tai {CONTINUE_BTN}")
    inst.tap(*CONTINUE_BTN)
    pause(AFTER_CONTINUE, log, "cho banh xe chon ngay hien ra")

    # Moi may mot ngay sinh khac nhau: 4 tai khoan cung ngay sinh la mot dau
    # hieu de nhan ra chung di cung mot nhom.
    for name, (x, y) in WHEELS.items():
        times = random.randint(*SCROLLS[name])
        dy = SCROLL_DY[name]
        log(f"banh xe {name} tai ({x}, {y}): cuon {times} nac, dy={dy}")
        inst.scroll(x, y, times=times, dy=dy, pause=SCROLL_PAUSE * SLOW)

    pause(AFTER_WHEELS, log, "sau khi cuon xong")
    log(f"bam xac nhan tai {SUBMIT_BTN}")
    inst.tap(*SUBMIT_BTN)
    pause(AFTER_SUBMIT, log, "cho man dang ky ve xong")

    lap("xong man xac minh tuoi")

    # 6. Man dang ky: username + gioi tinh.
    #    Cap username/password sinh va luu vao SQLite TRUOC khi go, de neu may
    #    ao chet giua chung thi van con ban ghi ma tra lai -- chu khong mat
    #    mot tai khoan da tao tren Roblox ma khong biet mat khau la gi.
    acc = STORE.new_account(ld_index=inst.index)
    log(f"tai khoan moi: {acc.username} / {acc.password}")

    log(f"bam o username tai {USERNAME_FIELD}")
    inst.tap(*USERNAME_FIELD)
    pause(STEP_PAUSE)

    inst.text(acc.username)
    pause(STEP_PAUSE)

    gender, pos = random.choice([("nu", GENDER_FEMALE), ("nam", GENDER_MALE)])
    log(f"gioi tinh: {gender} tai {pos}")
    inst.tap(*pos)
    pause(STEP_PAUSE)

    log(f"bam Continue tai {SIGNUP_CONTINUE}")
    inst.tap(*SIGNUP_CONTINUE)
    pause(STEP_PAUSE)

    STORE.update(acc.username, gender=gender, status="username_set")
    lap(f"xong man dang ky ({acc.username})")

    # 7. Man "Create Account": nhap mat khau roi bam Done.
    #    Mat khau sinh ra da thoa ca ba luat man hinh nay kiem: >= 8 ky tu,
    #    khong don gian, khong trung username (xem random_password()).
    pause(PASSWORD_WAIT, log, "cho man tao mat khau")

    log(f"go mat khau ({len(acc.password)} ky tu)")
    inst.text(acc.password)
    pause(STEP_PAUSE)

    log(f"bam Done tai {DONE_BTN}")
    inst.tap(*DONE_BTN)
    pause(STEP_PAUSE)

    # "submitted" = da bam het cac nut, KHONG phai "tao tai khoan thanh cong".
    # Chua co buoc nao doc man hinh de xac nhan Roblox chap nhan.
    STORE.update(acc.username, status="submitted")
    lap(f"xong man mat khau ({acc.username})")

    # 8. Lay cookie .ROBLOSECURITY ngay tren may nay.
    #    Biet chac may nay dang login acc.username (vua tao), nen khong can API
    #    de dinh danh -- API chi con vai tro XAC NHAN. Buoc nay cung la cach
    #    duy nhat biet dang ky co that su thanh cong hay khong.
    pause(COOKIE_WAIT, log, "cho Roblox login xong truoc khi lay cookie")
    ck, reason = inst.extract_cookie()
    if not ck:
        # Khong co cookie = login chua thanh cong (captcha, treo, hoac chua root).
        STORE.update(acc.username, status=f"failed_{reason}")
        log(f"KHONG lay duoc cookie ({reason}) -> danh dau failed_{reason}")
    elif VERIFY_COOKIE:
        info = inst.verify_cookie(ck)
        if info and info["name"].lower() == acc.username.lower():
            STORE.update(acc.username, cookie=ensure_warning_prefix(ck),
                         roblox_user_id=info["id"], verified_at=time.time(),
                         status="done")
            log(f"cookie OK, verify: {info['name']} (id={info['id']})")
        elif info:
            # Cookie song nhung username khac -> may login nham acc khac.
            STORE.update(acc.username, cookie=ensure_warning_prefix(ck),
                         note=f"cookie thuoc {info['name']}", status="mismatch")
            log(f"CANH BAO: cookie thuoc {info['name']}, khong phai {acc.username}")
        else:
            STORE.update(acc.username, cookie=ensure_warning_prefix(ck),
                         status="cookie_unverified")
            log("lay duoc cookie nhung verify that bai")
    else:
        STORE.update(acc.username, cookie=ensure_warning_prefix(ck), status="done")
        log("cookie OK (khong verify)")

    lap(f"xong lay cookie ({acc.username})")

    # ------- THAO TAC TIEP THEO DAT O DAY -------

    return acc.username


def flow(inst: Instance, log: Log) -> None:
    """Chay one_round lap di lap lai tren cung mot may ao.

    Moi vong bat dau bang mot may ao vua boot: tat han roi bat lai chac chan
    hon la dung tiep phien cu, vi Roblox con giu phien dang nhap cua tai khoan
    vua tao -- vong sau se khong ra man dang ky nua.
    """
    made: list[str] = []
    fails = 0
    n = 0
    while not STOP.is_set():
        n += 1
        log(f"===== vong {n}" + (f"/{ROUNDS}" if ROUNDS else "") + " =====")
        try:
            made.append(one_round(inst, log))
            fails = 0
        except Exception as exc:
            fails += 1
            log(f"vong {n} HONG ({fails}/{MAX_FAILS}): {type(exc).__name__}: {exc}")
            # Vong hong khong duoc keo do ca may ao: mot lan VPN cham hay
            # Roblox ve lau la chuyen thuong. Chi bo cuoc khi hong LIEN TIEP.
            if fails >= MAX_FAILS:
                log(f"hong {MAX_FAILS} vong lien tiep -> dung may ao nay")
                raise
        finally:
            # Tat may ao du vong vua roi thanh hay bai -- vong sau phai bat dau
            # tu may sach. Loi luc tat khong duoc de nuot mat loi that o tren.
            try:
                log(f"doi {ROUND_PAUSE}s roi tat may ao")
                STOP.wait(ROUND_PAUSE)
                inst.stop()
                # settle=0: cho them giay chi can truoc khi COPY o dia.
                inst.console.wait_stopped(inst.index, settle=0)
            except Exception as exc:
                log(f"tat may ao khong sach: {type(exc).__name__}: {exc}")

        if ROUNDS and n >= ROUNDS:
            break
        if STOP.is_set():
            break
        # Rai ngau nhien de 4 may khong cung boot lai mot luc.
        wait = random.uniform(0, RESTART_JITTER)
        log(f"nghi {wait:.0f}s truoc vong sau")
        STOP.wait(wait)

    log(f"dung sau {n} vong, tao duoc {len(made)} tai khoan: {made}")


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
    # Khai bao o dau ham: Python doi `global` phai dung TRUOC moi lan dung ten
    # do trong ham, ma ROUNDS/ROUND_PAUSE con duoc dung lam default cho argparse.
    global STORE, ROUNDS, ROUND_PAUSE, SLOW

    ap = argparse.ArgumentParser()
    ap.add_argument("--clone", action="store_true", help="clone cho du 4 may truoc khi chay")
    ap.add_argument("--dump-ui", nargs="?", const=VPN_PKG, metavar="PACKAGE",
                    help=f"mo package roi in cay giao dien va thoat "
                         f"(mac dinh {VPN_PKG}; thu {ROBLOX_PKG} de xem game "
                         f"co lo node nao khong)")
    ap.add_argument("--dump-index", type=int, default=None,
                    help="may ao nao de dump (mac dinh: may goc)")
    ap.add_argument("--ldconsole", default=LDCONSOLE)
    ap.add_argument("--rounds", type=int, default=ROUNDS,
                    help="so vong moi may ao chay (0 = khong gioi han, Ctrl+C de dung)")
    ap.add_argument("--round-pause", type=float, default=ROUND_PAUSE,
                    help=f"giay cho sau khi bam Done truoc khi tat may ao "
                         f"(mac dinh {ROUND_PAUSE})")
    ap.add_argument("--slow", type=float, default=SLOW, metavar="HESO",
                    help="nhan moi moc cho voi he so nay (vd 1.5 = cho lau hon 50%%)")
    ap.add_argument("--db", default=DB_PATH,
                    help=f"file SQLite giu username/password (mac dinh {DB_PATH})")
    ap.add_argument("--stagger", type=float, default=STAGGER)
    ap.add_argument("--clear-clones", action="store_true",
                    help="chi xoa du lieu Roblox tren clone, giu nguyen may goc")
    ap.add_argument("--keep-roblox-data", action="store_true",
                    help="khong xoa du lieu Roblox tren may nao ca")
    ap.add_argument("--no-arrange", action="store_true",
                    help="khong keo cua so, de LDPlayer tu dat")
    ap.add_argument("--list-windows", action="store_true",
                    help="in moi cua so dang mo roi thoat (de tim dung tieu de)")
    ap.add_argument("--no-tune", action="store_true",
                    help="khong dung toi global setting cua LDPlayer")
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

    ROUNDS, ROUND_PAUSE, SLOW = args.rounds, args.round_pause, args.slow
    if SLOW != 1.0:
        print(f"He so cho: x{SLOW}")
    STORE = AccountStore(args.db)
    print(f"Kho tai khoan: {args.db} (dang co {STORE.count()} ban ghi)")

    if not args.no_tune:
        # Bot tai chung cho ca LDPlayer: 4 may ao boot cung luc la nghen dia va
        # CPU, day la phan lon trong ~83s cho boot. Day la SETTING CHUNG cua
        # LDPlayer, khong phai rieng may ao nao -- dung --no-tune de khong dung.
        console.global_setting(fps=30, audio=False, fast_play=True)
        print("Da dat global setting: fps=30, audio=tat, fastplay=bat "
              "(--no-tune de bo qua)")

    if args.dump_ui:
        pkg = args.dump_ui
        idx = args.dump_index
        if idx is None:
            src = console.find(SOURCE)
            if src is None:
                print(f"[FAIL] khong co may ao {SOURCE!r}")
                return 1
            idx = src.index
        inst = Instance(console, idx)
        inst.start()
        inst.start_app_adb(pkg)
        time.sleep(5)

        nodes = inst.ui_nodes()
        useful = [n for n in nodes if n["clickable"] or n["text"] or n["desc"]]
        print(f"\nindex={idx}, {pkg}: {len(nodes)} node, "
              f"{len(useful)} co text/desc/bam duoc\n")
        for n in useful:
            print(f"  text={n['text']!r:30} desc={n['desc']!r:25} "
                  f"id={n['id'].split('/')[-1]!r:22} click={n['clickable']} @{n['center']}")

        if len(useful) <= 2:
            # App ve bang game engine chi lo ra mot SurfaceView duy nhat.
            print("\n-> Gan nhu khong co node nao. App ve bang engine rieng chu")
            print("   khong dung widget Android, uiautomator khong nhin thay gi ben trong.")
            print("   Phan nay phai dieu khien bang anh mau: inst.tap_image(...).")
            print(f"\n   Lay anh de cat mau:")
            port = 5555 + idx * 2
            print(f'   "C:\\LDPlayer\\LDPlayer9\\adb.exe" -s 127.0.0.1:{port} '
                  f'exec-out screencap -p > shot.png')
        else:
            print("\n-> Co node doc duoc: dung inst.tap_node(text=..., res_id=...)")
            print("   chac chan hon anh mau nhieu, va khong phu thuoc do phan giai.")
        return 0

    instances = build_instances(console, args.clone)

    if not args.no_arrange:
        for slot, inst in enumerate(instances):
            WINDOW_SLOT[inst.index] = slot
        print(f"Xep cua so: {WINDOW_COLS} cot, moi may mot o "
              f"(be rong do luc chay, khong dat cung)")

    # Mac dinh XOA tren moi may: moi lan chay la mot phien Roblox sach. Muon
    # giu thi phai noi ro bang co.
    if args.keep_roblox_data:
        print("Khong xoa du lieu Roblox (--keep-roblox-data)")
    elif args.clear_clones:
        # instances[0] la may goc.
        CLEAR_ROBLOX_ON.update(i.index for i in instances[1:])
        print(f"Se xoa {ROBLOX_PKG} tren clone {sorted(CLEAR_ROBLOX_ON)} "
              f"(chi app nay, khong dung {VPN_PKG})")
    else:
        CLEAR_ROBLOX_ON.update(i.index for i in instances)
        print(f"Se xoa {ROBLOX_PKG} tren may {sorted(CLEAR_ROBLOX_ON)} "
              f"(chi app nay, khong dung {VPN_PKG})")
    print()

    # Tat dong loat TRUOC khi vao vong song song. `quit` re va khong ton CPU,
    # nen khong can gian cach; de trong flow() thi moi thread phai doi luot
    # stagger cua minh roi moi bat dau tat -- cong them ca phut vo ich.
    if not args.reuse:
        running = [i for i in instances if console.is_running(i.index)]
        if running:
            print(f"Tat {len(running)} may ao dang chay truoc khi bat lai...")
            for i in running:
                console.quit(i.index)
            for i in running:
                # settle=0: cho them giay chi can truoc khi COPY o dia, con bat
                # lai thi khong.
                console.wait_stopped(i.index, settle=0)
            print("da tat xong\n")

    print(f"Vong lap: {ROUNDS or 'khong gioi han'} vong/may ao, "
          f"cho {ROUND_PAUSE:.0f}s sau khi bam Done" +
          ("" if ROUNDS else "  (Ctrl+C de dung)"))

    t_start = time.monotonic()
    try:
        results = run_parallel(instances, flow, stagger=args.stagger)
    except KeyboardInterrupt:
        # Bao cac thread dung SAU khi xong vong hien tai. Cat ngang giua chung
        # se bo lai may ao dang bat va mot ban ghi tai khoan do dang.
        STOP.set()
        print("\n\nCtrl+C -- cho cac may ao xong vong hien tai roi dung...")
        print("(Ctrl+C lan nua de thoat ngay, may ao se con bat)")
        return 130

    dt = time.monotonic() - t_start
    print(f"\nTong thoi gian: {dt:.0f}s")
    print(f"Kho tai khoan: {STORE.count()} ban ghi "
          f"({STORE.count('submitted')} da bam het, "
          f"{STORE.count('new') + STORE.count('username_set')} do dang)")
    return report(results)


if __name__ == "__main__":
    sys.exit(main())
