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

from ldauto import (AccountStore, Emulator, Farm, Instance, LDConsole, Log,  # noqa: E402
                    Spec, ensure_warning_prefix, open_emulator, report,
                    resolve_cli, run_parallel)
from ldauto import window  # noqa: E402

# --------------------------------------------------------------------------
# Chuong trinh dong lenh cua emulator. Dua duong dan nao thi dung emulator do:
# dnconsole.exe / ldconsole.exe -> LDPlayer, memuc.exe -> MEmu (xem open_emulator).
# LDCONSOLE la duong dan MAC DINH (ten giu nguyen cho code cu) -- hien la MEmu.
# Muon ve LDPlayer: r"C:\LDPlayer\LDPlayer9\dnconsole.exe".
MEMUC = r"C:\Program Files\Microvirt\MEmu\memuc.exe"
LDCONSOLE = MEMUC

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

# Doi location moi lan ket noi -> moi acc mot IP.
# ExpressVPN la app that -> UU TIEN uiautomator (tap theo text). Toa do pixel chi
# la FALLBACK khi khong doc duoc widget. Chon random 1 nuoc trong danh sach hien.
VPN_OPEN_WAIT = 6             # giay cho ExpressVPN mo
# True  = KHONG doi nuoc: mo app, doi no tu ket noi; AUTOCONNECT_WAIT giay ma
#         chua len thi bam nut Connect. Khong bao gio bam Change / chon nuoc.
# False = doi nuoc moi vong (Change -> All Locations -> random nuoc).
# GUI dat co nay tu o tich "VPN tu ket noi".
VPN_AUTO_ONLY = False
# True = BO QUA han ExpressVPN: khong mo app, khong doi VPN len, vao thang
# Roblox. Dung khi VPN da bat o tang may tinh (PC). Bat ca hai co thi co nay
# thang. GUI dat tu o tich "Bo qua VPN".
VPN_SKIP = False
VPN_STEP_WAIT = 5            # giay giua cac buoc doi location
VPN_CHANGE_BTN = (315, 350)   # fallback: nut "Change" (anh 5)
VPN_ALL_TAB = (300, 115)      # fallback: tab "ALL LOCATIONS" (anh 6)
VPN_COUNTRY_ROWS = [          # fallback: cac hang nuoc
    (120, 224), (120, 282), (120, 339), (120, 396),
]
# Hop thoai "Changing Location?" hien SAU khi chon nuoc, nhung CHI khi VPN dang
# ket noi san -- doi location luc dang tat thi khong co hop thoai nao. Vi vay
# phai nhan dien hop thoai truoc khi bam, khong bam mu theo toa do.
VPN_DIALOG_TITLE = "Changing Location"
VPN_DIALOG_TIMEOUT = 12       # giay toi da cho hop thoai hien ra
VPN_CONTINUE_BTN = (279, 298) # fallback: nut Continue trong hop thoai (400x500)
# --- Danh sach nuoc: gom TOAN BO roi random tren tap day du ----------------
# Khong random tren "nhung nuoc dang hien" duoc: man 400x500 chi thay 4-6 hang
# dau, va ExpressVPN xep danh sach co dinh -> lan nao cung quanh quan may nuoc
# do. Phai cuon het mot luot de biet co nhung nuoc nao.
#
# Danh sach giong het nhau tren moi may ao va khong doi, nen chi gom MOT LAN
# roi dung chung cho ca farm.
VPN_LIST_ANCHOR = (200, 300)   # diem dat ngon tay de cuon trong danh sach
VPN_LIST_SCROLL_DY = -280      # am = ngon tay di len = danh sach chay xuong
VPN_LIST_MAX_SCROLLS = 60      # tran an toan cho _collect_countries (dump)
VPN_LIST_ENOUGH = 20
VPN_LIST_SETTLE = 0.8          # giay cho danh sach dung han truoc khi doc
# Random country trong flow: cuon ngau nhien 0..N nac roi boc dai 1 nuoc dang hien.
# 14 = so nac cham toi cuoi danh sach (Vietnam) do dump --collect thay 80 nuoc.
VPN_RANDOM_MAX_SCROLLS = 14
# Chu tren man danh sach KHONG phai ten nuoc -- loai ra khi gom.
VPN_LIST_CHROME = {
    "All Locations", "Recommended", "Recent", "Favorites", "Search",
    "Smart Location", "VPN Locations", "Back", "Done", "Cancel", "Continue",
    "Add-ons", "Speed Test", "Help", "Profile", "VPN",
    "All Regions", "Sort: Endpoints", "ALL LOCATIONS", "RECOMMENDED",
}
# Nuoc khong bao gio chon (Roblox bi chan / kiem duyet, va UK, US). Boc trung
# thi BOC LAI nuoc khac. Viet thuong; so khop CA TEN chu khong so "co chua":
# "oman" nam trong "Romania". ExpressVPN viet ten khac di thi them cach viet
# do vao day.
VPN_BLOCKED = {
    "vietnam", "viet nam",
    "turkey", "türkiye", "turkiye",
    "china",
    "egypt",
    "russia", "russian federation",
    "iraq",
    "algeria",
    "qatar",
    "oman",
    "palestine", "palestinian territories",
    "united kingdom", "uk",
    "united states", "us", "usa",
}

_country_cache: "list[str] | None" = None      # ten nuoc, theo thu tu trong list
_country_step: "dict[str, int]" = {}           # ten -> so nac cuon de thay no
_country_lock = threading.Lock()

# Doc trang thai tu chinh dong chu do. Dung \b: 'Unprotected' chua 'protected',
# con 'Not connected' / 'Disconnected' thi chua 'connected' -- so bang `in` la
# nham ca hai chieu.
VPN_ON_RE = re.compile(r"\bprotected\b", re.I)
VPN_OFF_RE = re.compile(r"\bnot\b|\bdisconnect", re.I)
# "Connecting...", "Reconnecting...": dang noi do, bam nut Connect luc nay la HUY.
VPN_BUSY_RE = re.compile(r"connecting", re.I)


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
ROBLOX_SETTLE = 20           # giay cho Roblox ve xong truoc khi bam
CONTINUE_BTN = (200, 323)    # Create Account
AFTER_CONTINUE = 7           # giay cho banh xe chon ngay hien ra

WHEELS = {                   # ba banh xe chon ngay sinh
    "thang": (107, 222),     # truoc: y=244 (nam dung vach duoi dong dang chon)
    "ngay":  (217, 222),
    "nam":   (313, 222),
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
AFTER_WHEELS = 6             # giay cho sau khi cuon xong
SUBMIT_BTN = (200, 369)      # nut "Confirm Birthday". truoc: (197, 394) -- nam
                             # duoi mep nut (y=388), bam truot -> bang khong dong
SUBMIT_BTN_2 = (200, 385)   # bam lai lan 2 cho chac chan
# Cho man dang ky ve XONG sau khi xac nhan ngay sinh. Truoc day khong co buoc
# cho nao o day: bam xac nhan xong la bam ngay o username, trong khi man hinh
# con dang chuyen -> cu bam roi vao khoang khong.
AFTER_SUBMIT = 16

# --- Man dang ky sau khi qua xac minh tuoi -------------------------------
# Cung he toa do 400x500 nhu tren.
STEP_PAUSE = 4               # giay giua moi thao tac
# Man "Create Account" DOI BO CUC sau moi thao tac, va day la cho de sai nhat.
# Ba trang thai, do tu anh chup that o 400x500:
#
#   A. vua vao man                 B. sau khi go username        C. sau khi chon gender
#      Birthday  (200, 214)           (Birthday bi ban phim         Birthday  (200, 131)
#      Username  (201, 286)            day len, bien mat)           Username  (201, 202)
#      Gender    (113/288, 370)       Username  (201, 162)          Gender    (113/288, 290)
#      Continue  (200, 461)           3 dong kiem tra ten           Continue  (200, 379)
#                                     Gender    (113/288, 308)
#                                     Continue  (200, 402)
#
# Flow di A -> B -> C, nen moi hang so phai lay o dung trang thai no duoc bam:
#   bam Username   luc dang o A
#   bam Gender     luc dang o B  (vua go xong, ban phim con mo)
#   bam Continue   luc dang o C  (chon gender xong, ban phim dong lai)
#
# Cot x khong doi qua ca ba trang thai -- chi co cot y chay.
USERNAME_FIELD = (200, 260)  # trang thai A
GENDER_FEMALE = (109, 292)   # trang thai B, icon ben trai
GENDER_MALE = (285, 292)     # trang thai B, icon ben phai
SIGNUP_CONTINUE = (200, 370) # trang thai C
# Bam Continue nhieu lan, cach nhau mot khoang: lan dau hay khong an (man hinh
# chua san sang nhan cham). pause() nhan he so SLOW.
SIGNUP_CONTINUE_TAPS = 3     # tong so lan bam
SIGNUP_CONTINUE_GAP = 6      # giay giua hai lan bam
SIGNUP_CONTINUE_LAST_GAP = 38  # rieng truoc lan bam CUOI: cho lau hon
# Lan 2 tro di bam vao TAM nut Continue, do tu anh chup man Create Account
# (quy ve 400x500 sau khi bo khung cua so MEmu; doi chieu: o Gender ra dung
# y=292 nhu dang dung). Nut trai tu y~369 toi y~401 -- toa do lan 1 (y=370)
# nam sat MEP TREN cua nut, nen hay truot.
SIGNUP_CONTINUE_RETRY = (200, 385)
# Lan bam CUOI khong bam mot cu ma SPAM ca loat quanh SIGNUP_CONTINUE_RETRY. Moi
# cu adb input tap tu no da mat vai tram ms, nen ca loat ~1-2s; log in thoi gian
# that de chinh SPAM_GAP. Rai +-5px van nam trong nut (y~369..401).
SIGNUP_CONTINUE_SPAM = (3, 4)    # so cu, random.randint
SIGNUP_CONTINUE_SPAM_GAP = 0.2   # giay giua hai cu (khong nhan SLOW)
SIGNUP_CONTINUE_SPAM_JITTER = 5  # +-px moi cu
# Bam Continue lan cuoi xong thi bam Back mot lan (bam mu, khong nhin man hinh)
# roi moi vao luong nhap mat khau.
SIGNUP_BACK_WAIT = 5         # giay cho truoc khi bam Back
AFTER_SIGNUP_BACK = 5        # giay cho sau khi bam Back
# Sau cu Back do, bang passkey (xem duoi) VAN CON thi _dismiss_passkey bam tiep;
# dong duoc thi cho POST_SIGNUP_WAIT giay cho man mat khau ve xong.
POST_SIGNUP_WAIT = 8
# Tren MEmu, bam Continue xong thi hay co bang he thong "Create passkey on
# another device?" de len che man Roblox. Khong doc duoc widget cua no, nen
# nhan ra bang ANH: bang la mot tam nen TRANG phu ~60% phia duoi man hinh,
# con moi man Roblox o buoc nay deu nen toi. Thay bang thi bam Back cua he
# dieu hanh la dong.
PASSKEY_REGION = (0.08, 0.55, 0.92, 0.95)  # vung lay mau: x0, y0, x1, y1 theo ti le man hinh
PASSKEY_WHITE = 215          # diem "gan trang": ca ba kenh mau >= nguong nay
PASSKEY_MIN_FRAC = 0.5       # tu 50% diem lay mau gan trang tro len = bang dang mo
PASSKEY_TRIES = 3            # bam Back toi da bay nhieu lan
PASSKEY_RECHECK_WAIT = 8     # giay cho sau moi lan bam Back roi moi nhin lai

# --- Man "Security" (nhan giu de xac nhan la nguoi that) -----------------
# TAM THOI TAT. Dat lai True de bat buoc nay. Dung co thay vi comment code:
# code van duoc trinh bien dich doc nen khong muc dan, va bat lai chi sua 1 tu.
DO_SECURITY = False
# Hien ra SAU khi bam Continue o man dang ky, TRUOC man tao mat khau.
# Detect man Security bang MAU DIEM ANH (Roblox khong co widget tree, uiautomator
# thay rong). Nut "Press and hold" la thanh xanh navy to -> doi toi khi pixel tai
# HOLD_BTN thanh xanh roi moi nhan giu. Chi dung PIL (khong can cv2).
HOLD_BTN = (200, 155)         # tam nut "Press and hold" (400x500)
# Nut la xanh navy: kenh Blue troi hon Red va Green it nhat BUTTON_BLUE_GAP.
# Kiem tra tuong doi nay khong can biet chinh xac ma mau (khoi calib tung so).
BUTTON_BLUE_GAP = 40
SECURITY_DETECT_TIMEOUT = 60  # giay toi da cho man Security hien ra
SECURITY_POLL = 2             # giay giua moi lan kiem tra mau
HOLD_SECONDS = 17             # giu nut 17 giay
HOLD_REPEAT_WAIT = 17         # doi 17 giay giua lan giu 1 va lan giu 2
AFTER_HOLD = 20               # doi 20 giay sau lan giu cuoi, roi moi nhap mat khau

# --- Man "Create Account" / tao mat khau ---------------------------------
# Man nay tu focus san vao o mat khau -> go thang, khong can bam truoc.
# Do tu anh debug (khung hinh that 400x500). Man nay co HAI bo cuc:
#
#                          hint AN (o khong focus)   hint HIEN (o dang focus)
#   o Password             y 224..259                y 224..257
#   3 dong kiem tra        --                        y 268..321
#   Done                   y 288..334                y 347..395
#   dong "OR"              y 351..359                y 412..420
#   "Create a passkey"     y 377..424                y 438..485
#
# Hai vung Done KHONG giao nhau -> khong co diem nao bam trung ca hai. Go xong
# thi o con focus (hint hien); bam mot cu la o mat focus, hint an, Done nhay
# len. Nen bam HAI lan theo dung thu tu: vi tri CO hint truoc, vi tri hint AN
# sau. Dao nguoc la sai: cu dau lam hint an, cu sau bam vao cho Done da roi di.
PASSWORD_FIELD = (200, 241)  # tam o. truoc: y=228 -- chi cach mep tren (224) 4px
PASSWORD_FOCUS_WAIT = 2      # doi 2s sau khi bam o password truoc khi go
# Lan 1, bo cuc co hint. Lay CAO hon tam nut (371): neu hint da an san thi 371
# chi cach "Create a passkey" (377) 6px. 362 van trong Done (347..395), con
# luc hint an thi roi vao khoang trong duoi chu "OR", cach passkey 15px.
DONE_BTN_HINT = (200, 362)
DONE_BTN = (200, 315)        # lan 2, bo cuc hint an, trong Done (288..334)
# Chup man may ao de biet luc sap bam thi man hinh dang la gi. Anh la dung
# khung hinh 400x500 cua may ao -> do toa do thang tren anh. Thu muc nam canh
# accounts.db (chay exe thi la canh file exe). "" = tat rieng thu muc do.
DEBUG_SHOT_DIR = "debug_shots"   # ngay truoc khi bam o password
DEBUG_DONE_DIR = "debug_done"    # _1: truoc cu bam Done dau, _2: truoc cu thu hai

# Nhan chung cho MOI moc cho ben duoi (--slow). May yeu hoac chay nhieu may ao
# thi moi thu deu cham di theo cung mot ty le, khong can sua tung hang so.
SLOW = 1.0


def place_window(inst, log: "Log | None" = None) -> None:
    """Keo cua so may ao ve o cua no theo WINDOW_SLOT. Dung chung reg + login.

    Dung handle tu list2 (khong do theo tieu de vi 'bot1' nam trong 'bot10').
    Phai goi SAU khi may ao bat xong -- luc tat handle bang 0.
    """
    slot = WINDOW_SLOT.get(inst.index)
    if slot is None:
        return
    info = inst.console.find(inst.index)
    hwnd = info.top_window_handle if info else 0
    pos = window.slot_pos(hwnd, slot, cols=WINDOW_COLS,
                          origin=WINDOW_ORIGIN, gap=WINDOW_GAP)
    if pos is None and info and info.width:
        # Do khong duoc thi suy tu do phan giai may ao + CHROME (vien/tieu de/cot).
        w, h = info.width + CHROME[0], (info.height or 500) + CHROME[1]
        pos = (WINDOW_ORIGIN[0] + (slot % WINDOW_COLS) * (w + WINDOW_GAP[0]),
               WINDOW_ORIGIN[1] + (slot // WINDOW_COLS) * (h + WINDOW_GAP[1]))
    if pos and window.place_hwnd(hwnd, *pos):
        if log:
            log(f"cua so -> o {slot} tai {pos} (hwnd={hwnd})")
    elif log:
        log(f"khong keo duoc cua so, hwnd={hwnd} -- bo qua")


def pause(seconds: float, log: Log | None = None, why: str = "") -> None:
    """time.sleep co nhan he so SLOW, ton trong pause/stop."""
    _gate(log)              # dang pause thi dung o day truoc khi cho tiep
    t = seconds * SLOW
    if log and why:
        log(f"cho {t:.0f}s {why}")
    STOP.wait(t)


# --- Vong lap -------------------------------------------------------------
# Chay theo DOT: moi dot bat TAT CA may ao (nguon + clone), moi may mot vong,
# doi tat ca xong va tat het roi moi mo dot sau. Khong con kieu moi may tu lap
# rieng roi tu bat lai de "lap day".
ROUNDS = 0                   # so dot. 0 = chay khong gioi han, Ctrl+C de dung
ROUND_PAUSE = 8              # giay cho sau khi bam Done, truoc khi tat may ao
MAX_FAILS = 3                # so dot LIEN TIEP khong may nao chay het vong thi dung han
# Chi con luong login (roblox_login.py) dung: nghi ngau nhien giua hai tai khoan.
RESTART_JITTER = 14

# Dat khi nguoi dung Ctrl+C. Thread dang chay se xong vong hien tai roi dung,
# khong cat ngang giua chung de khoi bo lai may ao dang bat.
STOP = threading.Event()

# RESUME: SET = dang chay, CLEAR = tam dung. Cac thread di qua _gate() o dau moi
# vong va truoc moi buoc cho -> pause co hieu luc o ranh gioi buoc, khong cat
# ngang giua mot thao tac. Mac dinh SET (chay ngay).
RESUME = threading.Event()
RESUME.set()


def _gate(log: "Log | None" = None) -> None:
    """Chan lai khi dang pause; thoat ngay khi stop. Goi o cac diem an toan."""
    if RESUME.is_set() or STOP.is_set():
        return
    if log:
        log("tam dung (bam Tiep tuc de chay lai)")
    while not RESUME.wait(0.2):
        if STOP.is_set():
            return
    if log:
        log("tiep tuc")

# --- Lay cookie cuoi flow ------------------------------------------------
# Cho Roblox login xong han sau khi bam Done -> cookie moi duoc ghi vao DB
# cua WebView. Lay som qua thi chua co gi.
COOKIE_WAIT = 12
VERIFY_COOKIE = True         # goi API Roblox xac nhan cookie song + dung acc

DB_PATH = "accounts.db"
STORE: AccountStore | None = None   # tao o main(), moi thread dung chung
# --------------------------------------------------------------------------


# Moi hang nuoc trong danh sach la mot cum node:
#     View     (200, 200)  bam duoc   <- khung hang
#     TextView ( 94, 191)  "Bahamas"  <- ten nuoc, KHONG bam duoc, KHONG co id
#     TextView (135, 210)  "63 locations | > 3700 endpoints"   (nuoc lon)
#     TextView (135, 210)  "1 location"                        (nuoc nho!)
#     Button   (368, 200)  bam duoc   <- nut sao yeu thich, bam nham la hong
# Ten nuoc khong co resource-id va khong clickable, nen khong the nhan dien
# bang thuoc tinh cua rieng no. Dau hieu chac chan la DONG PHU DE ngay duoi.
#
# QUAN TRONG: nuoc nho chi co "1 location", KHONG kem "| > N endpoints".
# Bat buoc dau "|" thi bo sot ca duoi danh sach (Croatia, Cuba, Cyprus,
# Czechia, ... deu "1 location") -> gom xong tuong het som o ~31 nuoc.
# Nen phan "| > N endpoints" phai la TUY CHON.
_SUBTITLE_RE = re.compile(r"^\d+\s+locations?\b", re.I)


def _country_rows(nodes: list[dict]) -> list[tuple[str, tuple[int, int]]]:
    """[(ten nuoc, diem bam)] doc tu cay giao dien.

    Ghep cap theo thu tu: gap dong phu de thi node co chu ngay truoc no chinh
    la ten nuoc. Cach nay khong phu thuoc id hay clickable -- hai thu ma hang
    nuoc deu khong co.

    Diem bam la tam cua chinh o chu (x~94), nam trong khung hang va cach xa
    nut sao o x=368.
    """
    out: list[tuple[str, tuple[int, int]]] = []
    prev: tuple[str, tuple[int, int]] | None = None
    for n in nodes:
        t = n["text"].strip()
        if not t:
            continue
        if _SUBTITLE_RE.match(t):
            if prev and prev[0] not in VPN_LIST_CHROME:
                out.append(prev)
            prev = None
            continue
        prev = (t, n["center"])
    return out


def _scroll_list(inst: Instance, times: int = 1) -> None:
    """Cuon xuong trong danh sach nuoc."""
    inst.scroll(*VPN_LIST_ANCHOR, times=times, dy=VPN_LIST_SCROLL_DY,
                pause=VPN_LIST_SETTLE)


def _scroll_to_top(inst: Instance, sweeps: int = 12) -> None:
    """Ve dau danh sach. Vuot dai + nhanh, khong can chinh xac tung nac."""
    inst.scroll(*VPN_LIST_ANCHOR, times=sweeps,
                dy=-VPN_LIST_SCROLL_DY * 2, pause=0.15)


def _collect_countries(inst: Instance, log: Log,
                       max_scrolls: int = VPN_LIST_MAX_SCROLLS) -> list[str]:
    """Cuon het danh sach, tra ve moi ten nuoc doc duoc (giu thu tu).

    Cung ghi lai moi ten can bao nhieu nac cuon moi thay, de lan sau nhay
    thang toi do thay vi do lai tu dau.
    """
    global _country_cache
    with _country_lock:
        if _country_cache:
            return _country_cache

        log(f"gom danh sach nuoc: cuon toi da {max_scrolls} nac, "
            f"moi nac ~1s -- chi lam mot lan cho ca farm")
        names: list[str] = []
        empty_rounds = 0
        for step in range(max_scrolls):
            t0 = time.monotonic()
            try:
                nodes = inst.ui_nodes()
            except Exception as exc:
                log(f"  nac {step}: doc UI hong ({type(exc).__name__}) -- bo qua")
                nodes = []
            new = [name for name, _ in _country_rows(nodes)
                   if name not in _country_step]
            for t in new:
                _country_step[t] = step
                names.append(t)
            # In TUNG NAC: khong co dong nay thi ca phut khong thay gi, nhin y
            # het nhu treo va khong biet no dang o dau.
            log(f"  nac {step}: {len(nodes)} node, +{len(new)} nuoc moi "
                f"(tong {len(names)}) [{time.monotonic() - t0:.1f}s]"
                + (f" {new[:4]}" if new else ""))
            # Lay duoc ca danh sach ngay tu lan dump dau -> khoi cuon.
            if step == 0 and len(names) >= VPN_LIST_ENOUGH:
                log(f"  mot lan dump da ra {len(names)} nuoc -> lay het, khong can cuon")
                break
            # Hai lan cuon lien tiep khong ra ten moi = da toi cuoi danh sach.
            # Mot lan thi chua chac: co man hinh chi co tieu de.
            # BA nac lien tiep moi dung, khong phai hai: danh sach dai co the
            # co doan lap lai vi cuon chua lai, va dung som thi cat cut danh
            # sach ma khong biet -- lan truoc dung o 21 nuoc chinh vi kieu nay.
            empty_rounds = 0 if new else empty_rounds + 1
            if empty_rounds >= 3:
                log(f"  ba nac lien tiep khong ra ten moi -> het danh sach")
                break
            _scroll_list(inst)

        _country_cache = names
        log(f"gom duoc {len(names)} nuoc: {', '.join(names[:12])}"
            + (" ..." if len(names) > 12 else ""))
        return names


def _tap_country(inst: Instance, name: str, log: Log) -> bool:
    """Cuon toi nuoc `name` roi bam. True neu bam duoc."""
    hint = _country_step.get(name, 0)
    if hint:
        _scroll_list(inst, times=hint)      # nhay thang toi cho da biet
    # Nhay xong van phai doc lai de xac nhan: danh sach co the truot lech vai
    # hang. Tim khong thay thi cuon tiep tung nac.
    for extra in range(6):
        try:
            rows = dict(_country_rows(inst.ui_nodes()))
        except Exception:
            rows = {}
        if name in rows:
            log(f"chon nuoc: {name!r} tai {rows[name]} "
                f"(nac {hint}{'+' + str(extra) if extra else ''})")
            inst.tap(*rows[name])
            return True
        _scroll_list(inst)
    log(f"khong tim lai duoc {name!r} sau khi cuon")
    return False


def _pick_country(inst: Instance, log: Log) -> None:
    """Random: cuon ngau nhien 0..N nac roi boc dai 1 nuoc DANG HIEN ra bam.

    Don gian han gom ca danh sach: man All Locations mo moi lan la o dau list,
    nen cuon 0..32 nac dua ta toi mot cho ngau nhien, roi lay bat ky nuoc nao
    dang thay. Khong can biet truoc co bao nhieu nuoc.
    """
    n = random.randint(0, VPN_RANDOM_MAX_SCROLLS)
    if n:
        _scroll_list(inst, times=n)
    log(f"random: cuon {n} nac")

    for _ in range(3):
        try:
            rows = _country_rows(inst.ui_nodes())
        except Exception:
            rows = []
        rows = [(name, pos) for name, pos in rows if name not in VPN_LIST_CHROME]
        if not rows:
            break
        # Boc ngau nhien; trung nuoc bi chan thi bo no ra va BOC LAI trong cac
        # nuoc con lai dang hien, toi khi ra nuoc khong bi chan.
        pool = list(rows)
        while pool:
            name, pos = pool.pop(random.randrange(len(pool)))
            if name.strip().lower() not in VPN_BLOCKED:
                log(f"chon nuoc: {name!r} tai {pos}")
                inst.tap(*pos)
                return
            log(f"boc trung nuoc bi chan {name!r} -> boc lai")
        # Ca man hinh toan nuoc bi chan -> cuon them mot nac roi boc lai.
        _scroll_list(inst)

    # Khong doc duoc gi -> bam mu mot hang. Kem chac chan han, nen noi ro.
    x, y = random.choice(VPN_COUNTRY_ROWS)
    log(f"khong doc duoc nuoc nao (widget) -> bam toa do random ({x}, {y})")
    inst.tap(x, y)


def connect_vpn(inst: Instance, log: Log) -> None:
    """Bat VPN neu chua bat.

    Moc that su la interface tun co dia chi IP, khong phai chu tren man hinh:
    app bao 'Connected' ma khong co tun nghia la duong ham chua dung duoc.
    """
    if VPN_SKIP:
        # VPN chay o tang may tinh: trong may ao khong co tun nao de doi, va
        # mo ExpressVPN len chi them mot lop VPN chong len.
        log("bo qua VPN (VPN_SKIP): khong mo ExpressVPN, vao thang Roblox")
        return

    # ExpressVPN tu ket noi lai khi may ao khoi dong (thua tu may goc), nhung mat
    # vai chuc giay. Kiem tra mot lan ngay sau boot la qua som: tun chua len,
    # script tuong chua bat roi bam nut -- ma do la TOGGLE, tuc ngat mat cai
    # dang tu noi. Doi han ra truoc khi can thiep.
    # Poll re hon HAN so voi mo app: mot lenh `ip addr` moi 2 giay, doi lai
    # bo qua duoc ca start_app + uiautomator dump. Vong nay thoat NGAY khi tun
    # len, nen cho lau khong ton gi neu VPN len som.
    inst.start_app_adb(VPN_PKG)
    pause(VPN_OPEN_WAIT, log, "cho ExpressVPN mo")

    # Hop thoai "Connection request" cua he thong -- clone thuong da co consent.
    # O che do tu ket noi thi chi khop DUNG chu: khop mot phan co the trung mot
    # chu nao do tren man ExpressVPN co chua "ok" (vd "Tokyo") va thanh ra bam
    # vao app.
    _accept_vpn_dialog(inst, log, exact=VPN_AUTO_ONLY)

    if VPN_AUTO_ONLY:
        _auto_connect(inst, log)
    else:
        _change_location(inst, log)

    try:
        inst.wait_vpn(timeout=120)
    except TimeoutError:
        log("tun chua len sau 120s -> doi them 120s")
        inst.wait_vpn(timeout=120)
    log("VPN da len (tun co IP)")


def _accept_vpn_dialog(inst: Instance, log: Log, exact: bool) -> None:
    """Bam OK o hop thoai "Connection request" cua he thong neu no dang hien."""
    for label in ("OK", "Allow", "Dong y"):
        if inst.tap_node(text=label, exact=exact):
            log(f"da bam '{label}' o hop thoai VPN cua he thong")
            pause(2)
            break


def _auto_connect(inst: Instance, log: Log) -> None:
    """Che do VPN tu ket noi: doi app tu noi; khong tu noi thi bam nut Connect.

    Khong bao gio bam Change hay chon nuoc. Nut Connect la TOGGLE -- bam luc
    dang noi la ngat -- nen chi bam khi chac VPN dang TAT: tun chua len VA dong
    trang thai khong bao "Protected" hay "Connecting". Ham nay chi lo viec bam;
    viec doi tun len van o connect_vpn.
    """
    log(f"VPN tu ket noi: doi toi da {AUTOCONNECT_WAIT}s cho ExpressVPN tu noi")
    deadline = time.monotonic() + AUTOCONNECT_WAIT * SLOW
    while time.monotonic() < deadline and not STOP.is_set():
        if inst.vpn_connected():
            log("ExpressVPN da tu ket noi")
            return
        pause(2)

    try:
        nodes = inst.ui_nodes()
    except Exception:
        nodes = []
    st = inst.find_node(res_id=VPN_STATUS_ID, nodes=nodes)
    status = st["text"] if st else ""
    if status_says_on(status) or VPN_BUSY_RE.search(status):
        log(f"trang thai {status!r}: dang noi -> khong bam Connect, doi tiep")
        return
    btn = None
    for hint in VPN_CONNECT_HINTS:
        btn = inst.find_node(nodes=nodes, **hint)
        if btn:
            break
    if btn is None:
        log(f"VPN chua len (trang thai {status!r}) nhung khong thay nut Connect -> doi tiep")
        return
    log(f"VPN chua tu len (trang thai {status!r}) -> bam Connect tai {btn['center']}")
    inst.tap(*btn["center"])
    pause(2)
    # Bam Connect lan dau co the lam hien hop thoai xin quyen VPN cua he thong.
    _accept_vpn_dialog(inst, log, exact=True)


def _change_location(inst: Instance, log: Log) -> None:
    """Doi nuoc trong ExpressVPN: Change -> tab All Locations -> random nuoc."""
    # Doi location -> moi acc mot IP: Change -> tab All Locations -> random nuoc.
    # ExpressVPN la app that nen UU TIEN uiautomator (tap theo text/node); chi khi
    # khong doc duoc widget moi dung toa do pixel.
    if inst.tap_node(text="Change", timeout=15):
        log("bam Change (widget)")
    else:
        log("khong thay Change (widget) -> bam toa do")
        inst.tap(*VPN_CHANGE_BTN)
    pause(VPN_STEP_WAIT, log, "cho man VPN Locations")

    if inst.tap_node(text="All Locations", timeout=10):
        log("bam tab ALL LOCATIONS (widget)")
    else:
        log("khong thay tab (widget) -> bam toa do")
        inst.tap(*VPN_ALL_TAB)
    pause(VPN_STEP_WAIT, log, "cho danh sach nuoc")

    # Random tren TOAN BO danh sach, khong chi may nuoc dang hien tren man hinh.
    _pick_country(inst, log)

    # Xac nhan hop thoai "Changing Location?" neu no hien ra. Khong bam mu theo
    # toa do nhu cac buoc tren: hop thoai nay co the KHONG xuat hien (VPN dang
    # tat), va luc do mot cu bam vao giua man hinh se trung nut khac.
    deadline = time.monotonic() + VPN_DIALOG_TIMEOUT
    while time.monotonic() < deadline:
        try:
            nodes = inst.ui_nodes()
        except Exception:
            nodes = []
        if not any(VPN_DIALOG_TITLE in n["text"] for n in nodes):
            time.sleep(2)
            continue
        btn = inst.find_node(text="Continue", nodes=nodes)
        if btn:
            log(f"bam Continue o hop thoai {VPN_DIALOG_TITLE!r} tai {btn['center']}")
            inst.tap(*btn["center"])
        else:
            log(f"thay hop thoai nhung khong doc duoc nut -> bam toa do {VPN_CONTINUE_BTN}")
            inst.tap(*VPN_CONTINUE_BTN)
        pause(VPN_STEP_WAIT, log, "cho VPN noi lai sau khi doi location")
        break
    else:
        log(f"khong thay hop thoai {VPN_DIALOG_TITLE!r} -> bo qua")


def _passkey_sheet_open(inst: Instance) -> bool:
    """Bang "Create passkey ..." dang che man hinh? Nhan dien bang anh, chi can PIL.

    Lay mau mot luoi diem trong PASSKEY_REGION: phan lon gan trang thi la bang.
    Chup man hong thi coi nhu khong co bang.
    """
    try:
        img = inst.screenshot_pil()
    except Exception:
        return False
    w, h = img.size
    x0, y0, x1, y1 = PASSKEY_REGION
    n = 14                              # luoi 14x14 = 196 diem
    white = 0
    for i in range(n):
        for j in range(n):
            x = int(w * (x0 + (x1 - x0) * i / (n - 1)))
            y = int(h * (y0 + (y1 - y0) * j / (n - 1)))
            white += min(img.getpixel((x, y))[:3]) >= PASSKEY_WHITE
    return white / (n * n) >= PASSKEY_MIN_FRAC


def _dismiss_passkey(inst: Instance, log: Log) -> bool:
    """Dong bang he thong "Create passkey ..." neu no dang che Roblox. True neu da dong.

    Chi bam Back KHI THAY bang: bam Back luc khong co bang la lui khoi man dang
    ky. Bam xong thi cho PASSKEY_RECHECK_WAIT giay roi NHIN LAI: bang van con
    thi bam Back lan nua, toi da PASSKEY_TRIES lan.
    """
    if not _passkey_sheet_open(inst):
        return False
    for n in range(1, PASSKEY_TRIES + 1):
        log(f"thay bang 'Create passkey' (nen trang o nua duoi man hinh) -> bam Back lan {n}")
        inst.back()
        pause(PASSKEY_RECHECK_WAIT, log, "roi nhin lai xem bang passkey con khong")
        if not _passkey_sheet_open(inst):
            log("bang passkey da dong")
            return True
        log(f"sau {PASSKEY_RECHECK_WAIT}s bang passkey VAN CON")
    log(f"da bam Back {PASSKEY_TRIES} lan ma bang passkey van con -> di tiep")
    return True


def _debug_shot(inst: Instance, log: Log, folder: str, tag: str) -> None:
    """Luu anh man hinh may ao vao `folder`. Hong thi chi ghi log."""
    if not folder:
        return
    try:
        out = Path(folder)
        # Canh accounts.db chu khong theo thu muc dang chay: mo exe qua shortcut
        # thi thu muc dang chay co the la cho khac han.
        if not out.is_absolute() and STORE is not None:
            out = STORE.path.resolve().parent / out
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{time.strftime('%Y%m%d_%H%M%S')}_ld{inst.index}_{tag}.png"
        inst.screenshot_pil().save(path)
        log(f"da chup man hinh -> {path.resolve()}")
    except Exception as exc:
        log(f"chup man hinh hong ({type(exc).__name__}: {exc})")


def one_round(inst: Instance, log: Log) -> str | None:
    """Mot vong: bat may ao -> VPN -> Roblox -> tao xong mot tai khoan.

    Tra ve username vua tao, de nguoi goi ghi lai ket qua. Tra ve None khi
    cookie lay duoc thuoc tai khoan KHAC -- luc do acc vua sinh coi nhu chua
    tao duoc va ban ghi da bi xoa.
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

    # 1b. keo cua so ve o cua no (tach ra place_window de login dung chung).
    place_window(inst, log)

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
    time.sleep(1)
    log(f"bam lai xac nhan tai {SUBMIT_BTN_2} (chac chan)")
    inst.tap(*SUBMIT_BTN_2)
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

    # Lan 1 .. ke cuoi: moi lan bam mot cu.
    for k in range(1, SIGNUP_CONTINUE_TAPS):
        pos = SIGNUP_CONTINUE if k == 1 else SIGNUP_CONTINUE_RETRY
        log(f"bam Continue tai {pos} (lan {k}/{SIGNUP_CONTINUE_TAPS})")
        inst.tap(*pos)
        if k < SIGNUP_CONTINUE_TAPS - 1:
            pause(SIGNUP_CONTINUE_GAP, log, "truoc lan bam Continue tiep")

    # Lan cuoi: cho lau hon roi SPAM ca loat thay vi mot cu.
    pause(SIGNUP_CONTINUE_LAST_GAP, log, "truoc lan bam Continue cuoi")
    count = random.randint(*SIGNUP_CONTINUE_SPAM)
    log(f"spam Continue {count} cu quanh {SIGNUP_CONTINUE_RETRY} "
        f"(lan {SIGNUP_CONTINUE_TAPS}/{SIGNUP_CONTINUE_TAPS})")
    t = time.monotonic()
    inst.tap_spam(*SIGNUP_CONTINUE_RETRY, count=count,
                  jitter=SIGNUP_CONTINUE_SPAM_JITTER, interval=SIGNUP_CONTINUE_SPAM_GAP)
    log(f"spam xong sau {time.monotonic() - t:.1f}s")

    pause(SIGNUP_BACK_WAIT, log, "roi bam Back")
    log("bam Back")
    inst.back()
    pause(AFTER_SIGNUP_BACK, log, "sau khi bam Back")

    if _dismiss_passkey(inst, log):
        pause(POST_SIGNUP_WAIT, log, "cho man mat khau hien ra sau khi dong bang passkey")

    STORE.update(acc.username, gender=gender, status="username_set")
    lap(f"xong man dang ky ({acc.username})")

    # 6b. Man "Security" -- tam thoi tat bang DO_SECURITY.
    if not DO_SECURITY:
        log("bo qua man Security (DO_SECURITY=False)")
    else:
        # 6b. Man "Security": detect NUT XANH bang mau diem anh roi moi nhan giu.
        #     Roblox khong co widget tree -> khong dung uiautomator duoc. Doc mau
        #     pixel tai HOLD_BTN, doi toi khi no thanh xanh navy (nut hien ra) roi
        #     giu -> khong nhan vao khoang khong. Chi dung PIL, khong can cv2.
        x, y = HOLD_BTN
        deadline = time.monotonic() + SECURITY_DETECT_TIMEOUT * SLOW
        detected = False
        while time.monotonic() < deadline and not STOP.is_set():
            _gate(log)
            try:
                r, g, b = inst.pixel(x, y)
            except Exception:
                r = g = b = -999
            # nut xanh navy: Blue troi hon han Red va Green
            if b - r >= BUTTON_BLUE_GAP and b - g >= BUTTON_BLUE_GAP and b >= 70:
                detected = True
                log(f"detect nut Security (pixel xanh {(r, g, b)} tai {(x, y)})")
                break
            pause(SECURITY_POLL)
        if not detected:
            log(f"khong detect duoc nut Security sau {SECURITY_DETECT_TIMEOUT}s "
                f"-> giu mu tai {(x, y)}")

        log(f"nhan giu lan 1 {HOLD_SECONDS}s tai {(x, y)}")
        inst.hold(x, y, seconds=HOLD_SECONDS)
        pause(HOLD_REPEAT_WAIT, log, "cho giua 2 lan giu")
        log(f"nhan giu lan 2 {HOLD_SECONDS}s tai {(x, y)}")
        inst.hold(x, y, seconds=HOLD_SECONDS)
        pause(AFTER_HOLD, log, "cho sau lan giu cuoi, truoc khi nhap mat khau")
        lap("xong man Security")

    # 7. Man "Create Account": nhap mat khau roi bam Done.
    #    Mat khau sinh ra da thoa ca ba luat man hinh nay kiem: >= 8 ky tu,
    #    khong don gian, khong trung username (xem random_password()).
    #    Bam vao o password truoc khi go, khong trong vao autofocus cua man nay.
    _debug_shot(inst, log, DEBUG_SHOT_DIR, f"truoc_bam_password_{acc.username}")
    log(f"bam o password {PASSWORD_FIELD}")
    inst.tap(*PASSWORD_FIELD)
    pause(PASSWORD_FOCUS_WAIT)
    log(f"go mat khau ({len(acc.password)} ky tu)")
    inst.text(acc.password)
    pause(STEP_PAUSE)

    _debug_shot(inst, log, DEBUG_DONE_DIR, f"truoc_done_1_{acc.username}")
    log(f"bam Done lan 1 tai {DONE_BTN_HINT} (vi tri con 3 dong hint)")
    inst.tap(*DONE_BTN_HINT)
    pause(STEP_PAUSE)

    _debug_shot(inst, log, DEBUG_DONE_DIR, f"truoc_done_2_{acc.username}")
    log(f"bam Done lan 2 tai {DONE_BTN} (vi tri hint da an)")
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
            # Cookie song nhung username KHAC -> may dang login acc cu (thuong do
            # clone giu session may goc, hoac dang ky moi that bai). Acc vua sinh
            # coi nhu CHUA TAO DUOC -> xoa han ban ghi user/pass do, no vo nghia.
            log(f"CANH BAO: cookie thuoc {info['name']}, khong phai {acc.username} "
                f"-> xoa ban ghi (coi nhu chua tao duoc)")
            STORE.delete(acc.username)
            return None
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
    """MOT vong tren mot may ao, xong thi tat may. Vong lap nam o run_farm.

    run_farm chay theo DOT: bat tat ca may ao, moi may mot vong, doi tat ca
    xong va tat het roi moi mo dot sau. Ham nay la phan viec cua mot may trong
    mot dot. Vong hong thi nem loi ra de run_farm dem; may nay van duoc bat lai
    o dot sau.

    Tat may sau moi vong: Roblox con giu phien dang nhap cua tai khoan vua
    tao -- dung tiep thi vong sau khong ra man dang ky nua.
    """
    _gate(log)             # tam dung truoc khi bat may neu duoc yeu cau
    if STOP.is_set():
        return
    try:
        one_round(inst, log)
    finally:
        # Tat may ao du vong vua roi thanh hay bai -- dot sau phai bat dau tu
        # may sach. Loi luc tat khong duoc de nuot mat loi that o tren.
        try:
            log(f"doi {ROUND_PAUSE}s roi tat may ao")
            STOP.wait(ROUND_PAUSE)
            inst.stop()
            # settle=0: cho them giay chi can truoc khi COPY o dia.
            inst.console.wait_stopped(inst.index, settle=0)
        except Exception as exc:
            log(f"tat may ao khong sach: {type(exc).__name__}: {exc}")


def build_instances(console: Emulator, sources: list[str] | None = None,
                    do_clone: bool = False) -> list[Instance]:
    """Voi MOI may nguon: lay chinh no + clone CLONES may tu no.

    sources: danh sach ten may nguon, vd ["roblox", "roblox2"]. None -> [SOURCE].
    Clone dat ten theo nguon de khong dung nhau giua cac nguon:
        roblox  -> roblox_bot0, roblox_bot1, roblox_bot2
        roblox2 -> roblox2_bot0, ...
    """
    if sources is None:
        sources = [SOURCE]

    farm = Farm(console)
    instances: list[Instance] = []
    for src_name in sources:
        src = console.find(src_name)
        if src is None:
            # raise chu khong sys.exit: GUI chay ham nay o luong phu, va
            # sys.exit nem SystemExit -- thu `except Exception` cua GUI KHONG
            # bat. Luong chet lang le, nhat ky khong co dong loi nao.
            have = [i.name for i in console.list2()]
            raise RuntimeError(
                f"Khong co may nguon {src_name!r} tren {console.kind}. "
                f"Dang co: {have or 'khong may nao'}. "
                f"Sua lai danh sach Nguon cho khop.")

        if RESOLUTION:
            w, h, dpi = RESOLUTION
        else:
            w, h, dpi = src.width or 400, src.height or 500, src.dpi or 160
        print(f"Nguon: index={src.index} {src.name!r} {w}x{h}@{dpi}")

        instances.append(Instance(console, src.index))
        # MEmu: ep bat root tren TUNG clone. `memuc clone` reset mot phan cau
        # hinh (IMEI ve trong, MAC sinh moi -- do tren may that), khong chac
        # enable_su con giu. Mat root thi buoc lay cookie hong voi failed_no_root
        # ma khong bao gi ro rang. LDPlayer da chay on (root thua huong tu may
        # nguon) nen khong dung toi.
        extra = {"root": True} if console.kind == "memu" else {}
        spec = Spec(width=w, height=h, dpi=dpi, cpu=CPU, memory=MEMORY, extra=extra)
        for i in range(CLONES):
            name = f"{src_name}_{PREFIX}{i}"
            info = console.find(name)
            if info is None or do_clone:
                t0 = time.monotonic()
                action = "re-copying" if info else "chua co may ao, dang copy"
                print(f"[{name}] {action} tu {src_name}... (vai GB, doi vai phut)")
                inst = farm.ensure(name, spec, source=src.index)
                print(f"[{name}] xong sau {time.monotonic() - t0:.0f}s -> index={inst.index}")
            else:
                inst = Instance(console, info.index)
            instances.append(inst)

    print(f"Tong {len(instances)} may ao ({len(sources)} nguon): "
          f"{[i.index for i in instances]}\n")
    return instances


def run_farm(console: Emulator, *, sources: list[str] | None = None,
             do_clone: bool = False, arrange: bool = True,
             clear_mode: str = "all", reuse: bool = False,
             stagger: float | None = None) -> list:
    """Toan bo orchestration dung CHUNG cho CLI (main) va GUI (main.py).

    Cac global cau hinh (STORE, ROUNDS, ROUND_PAUSE, SLOW, CLONES) phai duoc dat
    TRUOC khi goi. Tach ra day de nut Start cua GUI chay Y HET script.

    clear_mode: 'all' xoa Roblox tren moi may | 'clones' chi clone | 'none' khong
                xoa. Xoa de moi vong la mot phien dang nhap sach.
    """
    instances = build_instances(console, sources, do_clone)

    if arrange:
        for slot, inst in enumerate(instances):
            WINDOW_SLOT[inst.index] = slot
        print(f"Xep cua so: {WINDOW_COLS} cot, moi may mot o")

    CLEAR_ROBLOX_ON.clear()
    if clear_mode == "none":
        print("Khong xoa du lieu Roblox")
    elif clear_mode == "clones":
        CLEAR_ROBLOX_ON.update(i.index for i in instances[1:])
        print(f"Se xoa {ROBLOX_PKG} tren clone {sorted(CLEAR_ROBLOX_ON)}")
    else:
        CLEAR_ROBLOX_ON.update(i.index for i in instances)
        print(f"Se xoa {ROBLOX_PKG} tren may {sorted(CLEAR_ROBLOX_ON)}")
    print()

    if not reuse:
        running = [i for i in instances if console.is_running(i.index)]
        if running:
            print(f"Tat {len(running)} may ao dang chay truoc khi bat lai...")
            for i in running:
                console.quit(i.index)
            for i in running:
                # Mot may khong tat duoc khong keo do ca run.
                try:
                    console.wait_stopped(i.index, timeout=90, settle=0)
                except TimeoutError:
                    console.quit(i.index)
                    print(f"[{i.index}] khong tat trong 90s -> bo qua")
            print("da tat xong\n")

        # Bat ADB debugging cho dung cac may sap chay. Dat o day vi day la luc
        # chac chan chung DANG TAT -- sua luc dang chay thi emulator ghi de mat.
        # MEmu luon bat ADB nen ham nay khong lam gi.
        n = console.ensure_adb([i.index for i in instances], log=print)
        if n:
            print(f"da bat ADB debugging cho {n} may ao\n")

    print(f"Chay theo dot: {ROUNDS or 'khong gioi han'} dot, moi dot bat ca "
          f"{len(instances)} may ao, moi may mot vong, xong het moi mo dot sau. "
          f"Cho {ROUND_PAUSE:.0f}s sau khi bam Done")

    t0 = time.monotonic()
    results: list = []
    n = 0
    dry = 0                # so dot LIEN TIEP khong may nao chay het vong
    while not STOP.is_set():
        _gate(print)       # tam dung giua hai dot neu duoc yeu cau
        if STOP.is_set():
            break
        n += 1
        t1 = time.monotonic()
        done_before = STORE.count("done")
        print(f"\n===== DOT {n}" + (f"/{ROUNDS}" if ROUNDS else "")
              + f": bat {len(instances)} may ao =====")
        results = run_parallel(instances, flow, trace=False,
                               stagger=STAGGER if stagger is None else stagger)
        ok = sum(1 for r in results if r.ok)
        print(f"===== het dot {n} sau {time.monotonic() - t1:.0f}s: {ok}/{len(results)} "
              f"may chay het vong, them {STORE.count('done') - done_before} tai khoan "
              f"co cookie =====")

        # Mot dot ma KHONG may nao chay het vong la co gi do hong chung (emulator,
        # mang, ADB). Lap lai mai chi dot may; dung sau MAX_FAILS dot nhu vay.
        dry = 0 if ok else dry + 1
        if dry >= MAX_FAILS:
            print(f"{MAX_FAILS} dot lien tiep khong may nao chay het vong -> dung")
            break
        if ROUNDS and n >= ROUNDS:
            break

    print(f"\nDung sau {n} dot. Tong thoi gian: {time.monotonic() - t0:.0f}s")
    print(f"Kho tai khoan: {STORE.count()} ban ghi "
          f"({STORE.count('submitted')} da bam het, "
          f"{STORE.count('new') + STORE.count('username_set')} do dang)")
    return results


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
    ap.add_argument("--ldconsole", "--console", dest="ldconsole", default=LDCONSOLE,
                    help="dnconsole.exe (LDPlayer) hoac memuc.exe (MEmu)")
    ap.add_argument("--emulator", choices=("ldplayer", "memu"), default=None,
                    help="ep loai emulator khi ten file khong theo quy uoc")
    ap.add_argument("--rounds", type=int, default=ROUNDS,
                    help="so dot; moi dot moi may ao chay mot vong "
                         "(0 = khong gioi han, Ctrl+C de dung)")
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

    console = open_emulator(args.ldconsole, kind=args.emulator)
    print(f"Emulator: {console.kind} ({console.path})")

    ROUNDS, ROUND_PAUSE, SLOW = args.rounds, args.round_pause, args.slow
    if SLOW != 1.0:
        print(f"He so cho: x{SLOW}")
    STORE = AccountStore(args.db)
    import os as _os
    print(f"Kho tai khoan: {_os.path.abspath(args.db)} "
          f"(dang co {STORE.count()} ban ghi)")

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
            port = console.adb_port_for(idx)
            print(f'   "{console.adb_exe or "adb.exe"}" -s 127.0.0.1:{port} '
                  f'exec-out screencap -p > shot.png')
        else:
            print("\n-> Co node doc duoc: dung inst.tap_node(text=..., res_id=...)")
            print("   chac chan hon anh mau nhieu, va khong phu thuoc do phan giai.")
        return 0

    clear_mode = ("none" if args.keep_roblox_data
                  else "clones" if args.clear_clones else "all")
    try:
        results = run_farm(console, do_clone=args.clone,
                           arrange=not args.no_arrange, clear_mode=clear_mode,
                           reuse=args.reuse, stagger=args.stagger)
    except KeyboardInterrupt:
        # Bao cac thread dung SAU khi xong vong hien tai. Cat ngang giua chung
        # se bo lai may ao dang bat va mot ban ghi tai khoan do dang.
        STOP.set()
        print("\n\nCtrl+C -- cho cac may ao xong vong hien tai roi dung...")
        print("(Ctrl+C lan nua de thoat ngay, may ao se con bat)")
        return 130
    return report(results)


if __name__ == "__main__":
    sys.exit(main())
