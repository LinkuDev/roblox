"""Luong LOGIN: dang nhap tai khoan CO SAN (user:pass) roi lay cookie.

Don gian hon luong tao acc: mo VPN -> mo Roblox -> Sign In -> nhap user -> Next
-> nhap pass -> Next -> doi -> check cookie (5s x 3 lan) -> xuat.

Dung chung DB (accounts.db), stats va xuat TXT nhu luong tao acc.

    python examples/roblox_login.py --file logins.txt
    (logins.txt: moi dong mot "user:pass")
"""

from __future__ import annotations

import argparse
import queue
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import roblox_flow as rf  # noqa: E402  (dung chung STOP/RESUME/pause/connect_vpn...)
from ldauto import (AccountStore, LDConsole, ensure_warning_prefix,  # noqa: E402
                    report, run_parallel)

# --- Toa do man login (400x500) - DO tu anh goc roi quy ty le ra 400x500 ---
# (do vi tri pixel nut xanh / o input trong anh, chia cho kich thuoc anh, x400/x500)
SIGN_IN_BTN = (200, 384)      # nut "Sign In" (ngay duoi Create Account) - anh 1
USERNAME_FIELD = (200, 180)   # o nhap username (vien xanh) - anh 2/3
USERNAME_NEXT = (200, 249)    # nut "Next" sau khi nhap username - anh 3
PASSWORD_NEXT = (200, 395)    # nut "Next" sau khi nhap password - anh 4

# Moi thao tac cach nhau 8s cho chac. Rieng buoc cuoi (Next o password) doi 20s.
ROBLOX_SETTLE = 8            # cho Roblox ve man dau
STEP_PAUSE = 8              # giay giua moi thao tac
PASSWORD_SCREEN_WAIT = 8     # cho man password hien sau khi Next username
COOKIE_WAIT = 20            # BUOC CUOI: doi 20s sau Next password roi moi check cookie
COOKIE_POLL = 5            # doi 5s giua cac lan check cookie
COOKIE_TRIES = 3           # check toi da 3 lan
STAGGER = 5

ROBLOX_PKG = rf.ROBLOX_PKG

STORE: AccountStore | None = None
QUEUE: "queue.Queue[tuple[str, str]]" = queue.Queue()


def login_one(inst, log, username: str, password: str) -> bool:
    """Dang nhap MOT tai khoan tren may `inst`, lay cookie. True neu co cookie."""
    STORE.add(username, password, ld_index=inst.index, status="login_new")

    # Xoa phien Roblox truoc -> chac chan ve man dang nhap, khong dinh acc cu.
    inst.clear_app(ROBLOX_PKG)
    inst.start_app_adb(ROBLOX_PKG)
    for _ in range(30):
        if inst.current_app() == ROBLOX_PKG:
            break
        time.sleep(2)
    rf.pause(ROBLOX_SETTLE, log, "cho Roblox ve man dau")

    log(f"bam Sign In tai {SIGN_IN_BTN}")
    inst.tap(*SIGN_IN_BTN)
    rf.pause(STEP_PAUSE)

    inst.tap(*USERNAME_FIELD)
    rf.pause(STEP_PAUSE)
    log(f"go username: {username}")
    inst.text(username)
    rf.pause(STEP_PAUSE)

    inst.tap(*USERNAME_NEXT)
    rf.pause(PASSWORD_SCREEN_WAIT, log, "cho man password")

    log("go password (o password tu focus san)")
    inst.text(password)
    rf.pause(STEP_PAUSE)
    inst.tap(*PASSWORD_NEXT)

    # Doi dang nhap xong roi check cookie: 20s, roi 5s x 3 lan.
    rf.pause(COOKIE_WAIT, log, "cho dang nhap xong")
    ck = None
    for i in range(COOKIE_TRIES):
        ck, reason = inst.extract_cookie()
        if ck:
            break
        log(f"chua co cookie (lan {i + 1}/{COOKIE_TRIES}: {reason}) -> doi {COOKIE_POLL}s")
        rf.pause(COOKIE_POLL)

    if not ck:
        STORE.update(username, status="login_failed")
        log(f"FAIL: {username} khong lay duoc cookie")
        return False

    info = inst.verify_cookie(ck)
    if info and info["name"].lower() == username.lower():
        STORE.update(username, cookie=ensure_warning_prefix(ck),
                     roblox_user_id=info["id"], verified_at=time.time(),
                     status="login_ok")
        log(f"OK: {username} (verify {info['name']})")
    elif info:
        STORE.update(username, cookie=ensure_warning_prefix(ck),
                     note=f"cookie thuoc {info['name']}", status="login_mismatch")
        log(f"CANH BAO: cookie thuoc {info['name']}, khong phai {username}")
    else:
        STORE.update(username, cookie=ensure_warning_prefix(ck), status="login_unverified")
        log(f"co cookie nhung verify fail: {username}")
    return True


def worker(inst, log) -> None:
    """Moi may: boot -> VPN -> rut tung acc tu QUEUE ra login toi khi het."""
    inst.start()
    rf.connect_vpn(inst, log)
    n = 0
    while not rf.STOP.is_set():
        rf._gate(log)
        if rf.STOP.is_set():
            break
        try:
            username, password = QUEUE.get_nowait()
        except queue.Empty:
            break
        n += 1
        log(f"===== acc {n}: {username} =====")
        try:
            login_one(inst, log, username, password)
        except Exception as exc:
            log(f"loi khi login {username}: {type(exc).__name__}: {exc}")
            if STORE is not None:
                STORE.update(username, status="login_error")
    log(f"xong, da xu ly {n} acc")


def load_logins(path: str | Path) -> list[tuple[str, str]]:
    accs = []
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        u, p = line.split(":", 1)
        if u.strip():
            accs.append((u.strip(), p.strip()))
    return accs


def run_login(console: LDConsole, accounts: list[tuple[str, str]],
              sources: list[str], *, db: str = "accounts.db",
              stagger: float = STAGGER, arrange: bool = True) -> list:
    """Chay login song song tren cac may (nguon + clone). Dung cho CLI va GUI."""
    global STORE, QUEUE
    STORE = AccountStore(db)
    QUEUE = queue.Queue()
    for a in accounts:
        QUEUE.put(a)
    print(f"Nap {QUEUE.qsize()} tai khoan can login")

    console.global_setting(fps=30, audio=False, fast_play=True)
    instances = rf.build_instances(console, sources)
    if arrange:
        for slot, inst in enumerate(instances):
            rf.WINDOW_SLOT[inst.index] = slot

    running = [i for i in instances if console.is_running(i.index)]
    if running:
        print(f"Tat {len(running)} may dang chay truoc khi bat lai...")
        for i in running:
            console.quit(i.index)
        for i in running:
            try:
                console.wait_stopped(i.index, timeout=90, settle=0)
            except TimeoutError:
                console.quit(i.index)

    results = run_parallel(instances, worker, stagger=stagger)
    print(f"\nKho: {STORE.count()} ban ghi | login OK: {STORE.count('login_ok')} | "
          f"fail: {STORE.count('login_failed')}")
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="file user:pass, moi dong mot acc")
    ap.add_argument("--ldconsole", default=rf.LDCONSOLE)
    ap.add_argument("--db", default="accounts.db")
    ap.add_argument("--source", action="append", metavar="NAME",
                    help="ten may nguon (lap lai de them nhieu, mac dinh 'roblox')")
    ap.add_argument("--clones", type=int, default=0,
                    help="so clone moi nguon (mac dinh 0 = chi dung may nguon)")
    ap.add_argument("--stagger", type=float, default=STAGGER)
    args = ap.parse_args()

    rf.CLONES = args.clones
    accounts = load_logins(args.file)
    if not accounts:
        print(f"[FAIL] Khong co user:pass nao trong {args.file}")
        return 1

    console = LDConsole(args.ldconsole)
    sources = args.source or [rf.SOURCE]
    try:
        results = run_login(console, accounts, sources, db=args.db, stagger=args.stagger)
    except KeyboardInterrupt:
        rf.STOP.set()
        rf.RESUME.set()
        print("\nCtrl+C -- cho cac may xong acc hien tai roi dung...")
        return 130
    return report(results)


if __name__ == "__main__":
    sys.exit(main())
