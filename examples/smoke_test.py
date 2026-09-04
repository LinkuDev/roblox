"""Kiem tra tung tang mot, dung ngay o tang dau tien hong.

Chay cai nay TRUOC setup_farm.py. Muc dich la khoanh vung loi:
neu tang 3 hong thi biet chac tang 1-2 da on.

    python examples/smoke_test.py "D:\\LDPlayer\\LDPlayer9\\ldconsole.exe"
"""

import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Kiem tra dependency TRUOC khi import ldauto, de bao loi de hieu
# thay vi nem traceback ModuleNotFoundError.
_missing = []
for _mod, _pkg in (("adbutils", "adbutils"), ("cv2", "opencv-python"),
                   ("numpy", "numpy"), ("PIL", "Pillow")):
    try:
        __import__(_mod)
    except ImportError:
        _missing.append(_pkg)
if _missing:
    print("[FAIL] Thieu thu vien:", ", ".join(_missing))
    print("\n-> Chay:  pip install -r requirements.txt")
    sys.exit(1)

from ldauto import LDConsole  # noqa: E402

OK, FAIL, WARN = "[ OK ]", "[FAIL]", "[WARN]"
_results: list[tuple[str, str]] = []


def step(n: int, title: str):
    print(f"\n--- {n}. {title} " + "-" * max(0, 50 - len(title)))


def record(status: str, msg: str) -> None:
    print(f"{status} {msg}")
    _results.append((status, msg))


def main(ldconsole_path: str, index: int = 0) -> int:
    # ---------------------------------------------------------------
    step(1, "Kiem tra cai dat LDPlayer")
    try:
        console = LDConsole(ldconsole_path)
        record(OK, f"ldconsole: {console.path}")
    except FileNotFoundError as e:
        record(FAIL, str(e))
        print("\n-> Sua duong dan. Thuong la:")
        print(r"   C:\LDPlayer\LDPlayer9\ldconsole.exe")
        print(r"   D:\Program Files\LDPlayer\LDPlayer9\ldconsole.exe")
        print("\n-> Neu ban dung ban repack ('Lite', 'By <ai do>') ma KHONG co")
        print("   ldconsole.exe thi ca thu vien nay vo dung -- moi ham deu goi no.")
        print("   Cac ban repack hay cat bot component. Phai cai ban chinh thuc.")
        return 1

    # Ban repack thuong cat bot file. Kiem tra nhung file thuc su can.
    ld_dir = console.path.parent
    for fname, why in (("dnplayer.exe", "chuong trinh chinh"),
                       ("adb.exe", "can cho ket noi ADB"),
                       ("ldopengl.dll", "render (co the vang o ban cu)")):
        f = ld_dir / fname
        record(OK if f.exists() else WARN, f"{fname:16} {'co' if f.exists() else 'THIEU'}  ({why})")

    # ---------------------------------------------------------------
    step(2, "Doc danh sach may ao (list2)")
    try:
        raw = console.run("list2")
        print("  stdout tho:")
        for line in raw.splitlines()[:5]:
            print(f"    {line!r}")

        infos = console.list2()
        if not infos:
            record(FAIL, "Khong parse duoc may ao nao. Gui stdout tho o tren de sua parser.")
            return 1

        record(OK, f"Parse duoc {len(infos)} may ao")
        for i in infos:
            res = f"{i.width}x{i.height}@{i.dpi}" if i.width else "(khong co cot resolution)"
            print(f"    index={i.index} name={i.name!r} running={i.running} {res}")

        # Day la gia dinh minh danh dau la CHUA VERIFY: LD9 co cot width/height/dpi.
        if infos[0].width is None:
            record(WARN, "list2 khong tra ve resolution -> ban dung LDPlayer 4? "
                         "Code van chay, chi la InstanceInfo.width = None.")
    except Exception:
        record(FAIL, "list2 hong:")
        traceback.print_exc()
        return 1

    target = next((i for i in infos if i.index == index), None)
    if target is None:
        record(FAIL, f"Khong co may ao index={index}. Chon index khac trong danh sach tren.")
        return 1

    # ---------------------------------------------------------------
    step(3, f"Bat may ao index={index} va doi boot")
    try:
        t0 = time.monotonic()
        console.launch(index)
        record(OK, "Da goi launch, dang doi sys.boot_completed...")
        console.wait_boot(index, timeout=240)
        record(OK, f"Android boot xong sau {time.monotonic() - t0:.0f}s")
    except Exception:
        record(FAIL, "launch/wait_boot hong:")
        traceback.print_exc()
        print("\n-> Neu may ao HIEN RA nhung wait_boot timeout thi loi o cho doc")
        print("   getprop qua ldconsole. Chay tay de xem no tra ve gi:")
        print(f'   "{console.path}" adb --index {index} --command "shell getprop sys.boot_completed"')
        return 1

    # ---------------------------------------------------------------
    step(4, "Ket noi ADB")
    from ldauto import Instance

    inst = Instance(console, index)
    print(f"  Doan cong theo quy uoc 5555+index*2 -> {inst.serial}")
    try:
        inst.connect(retries=5, delay=2)
        record(OK, f"ADB noi duoc: {inst.serial}")
    except Exception:
        record(FAIL, f"Khong noi duoc {inst.serial}")
        traceback.print_exc()
        print("\n-> Kiem tra cong that su bang:  adb devices")
        print("   Neu thay cong khac (vd 5585) thi truyen tay:")
        print(f"     Instance(console, {index}, adb_port=5585)")
        print("-> Neu bao 'adb server version doesn't match': ban co 2 ban adb.")
        print("   Chay:  adb kill-server   roi thu lai.")
        return 1

    # ---------------------------------------------------------------
    step(5, "Doc do phan giai (wm size)")
    try:
        raw_wm = inst.device.shell("wm size").strip()
        print(f"  stdout tho: {raw_wm!r}")
        w, h = inst.screen_resolution()
        record(OK, f"Parse duoc: {w}x{h}")
    except Exception:
        record(FAIL, "screen_resolution() hong -- gui stdout tho o tren de sua parser:")
        traceback.print_exc()

    # ---------------------------------------------------------------
    step(6, "Chup man hinh")
    try:
        t0 = time.monotonic()
        img = inst.screenshot()
        dt = time.monotonic() - t0
        out = Path("captures")
        out.mkdir(exist_ok=True)
        import cv2

        cv2.imwrite(str(out / "smoke.png"), img)
        record(OK, f"Chup xong {img.shape[1]}x{img.shape[0]} trong {dt*1000:.0f}ms "
                   f"(~{1/dt:.1f} fps) -> captures/smoke.png")
        if dt > 1.0:
            record(WARN, "Cham hon 1s/frame -- vong lap nhan dien anh se un tac.")
    except Exception:
        record(FAIL, "screenshot() hong:")
        traceback.print_exc()

    # ---------------------------------------------------------------
    step(7, "Thu thao tac (tap + phim)")
    try:
        inst.home()
        inst.tap_percent(50, 50)
        record(OK, "Gui duoc tap va keyevent (nhin man hinh xem co phan ung khong)")
    except Exception:
        record(FAIL, "tap/key hong:")
        traceback.print_exc()

    # ---------------------------------------------------------------
    print("\n" + "=" * 56)
    n_fail = sum(1 for s, _ in _results if s == FAIL)
    n_warn = sum(1 for s, _ in _results if s == WARN)
    print(f"KET QUA: {len(_results) - n_fail - n_warn} OK, {n_warn} canh bao, {n_fail} loi")
    for s, m in _results:
        if s != OK:
            print(f"  {s} {m}")
    print("=" * 56)
    return 1 if n_fail else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    sys.exit(main(sys.argv[1], idx))
