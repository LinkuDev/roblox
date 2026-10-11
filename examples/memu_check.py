"""Kiem tra MEmu tung tang mot, in NGUYEN VAN output cua memuc.

Backend MEmu (ldauto/memu.py) viet theo tai lieu memuc nhung CHUA chay tren may
that. File nay goi dung nhung lenh backend dung va in ca output tho lan ket qua
phan tich -- lech cho nao thi dan output do de sua.

Mac dinh CHI DOC, khong dung gi toi may ao:
    python examples\\memu_check.py

Bat mot may ao va thu ADB + root tren no:
    python examples\\memu_check.py --start 0

Thu clone (TAO mot may ao moi ten _memu_check roi XOA di):
    python examples\\memu_check.py --test-clone 0

Cau hinh may ao cho flow: 400x500 @160, bat root, doi ten:
    python examples\\memu_check.py --prepare 0 --rename roblox
"""

import argparse
import socket
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Kiem tra dependency truoc khi import ldauto, de bao loi de hieu.
try:
    import adbutils  # noqa: F401
except ImportError:
    print("[FAIL] Thieu adbutils -> pip install -r requirements.txt")
    sys.exit(1)

from ldauto import Instance, LDConsoleError  # noqa: E402
from ldauto.memu import MemuConsole  # noqa: E402

MEMUC = r"C:\Program Files\Microvirt\MEmu\memuc.exe"
OK, FAIL, WARN = "[ OK ]", "[FAIL]", "[WARN]"
results: list[tuple[str, str]] = []


def step(n: int, title: str) -> None:
    print(f"\n--- {n}. {title} " + "-" * max(0, 52 - len(title)))


def record(status: str, msg: str) -> None:
    print(f"{status} {msg}")
    results.append((status, msg))


def raw(memu: MemuConsole, *args) -> str:
    """Chay lenh memuc, in nguyen van, KHONG nem loi."""
    try:
        out = memu.run(*args)
        tag = ""
    except LDConsoleError as exc:
        out = str(exc)
        tag = "  <- memuc bao LOI"
    print(f"  $ memuc {' '.join(map(str, args))}{tag}")
    for line in (out.splitlines() or ["(khong in gi)"])[:12]:
        print(f"    {line!r}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--memuc", default=MEMUC)
    ap.add_argument("--start", type=int, metavar="INDEX",
                    help="bat may ao nay roi thu ADB + root")
    ap.add_argument("--test-clone", type=int, metavar="INDEX",
                    help="clone may ao nay thanh _memu_check roi xoa (CHAM, vai phut)")
    ap.add_argument("--prepare", type=int, metavar="INDEX",
                    help="dat 400x500 @160 + bat root cho may ao nay (TAT may ao truoc)")
    ap.add_argument("--rename", metavar="TEN",
                    help="kem --prepare: doi ten may ao (flow tim may nguon ten 'roblox')")
    args = ap.parse_args()

    # ------------------------------------------------------------------
    step(1, "Tim memuc.exe")
    try:
        memu = MemuConsole(args.memuc)
        record(OK, f"memuc: {memu.path}")
    except FileNotFoundError as exc:
        record(FAIL, str(exc))
        return 1
    for f in ("MEmu.exe", "adb.exe", "MemuHyperv VMs"):
        p = memu.install_dir / f
        record(OK if p.exists() else WARN, f"{f:16} {'co' if p.exists() else 'THIEU'}")

    # ------------------------------------------------------------------
    step(2, "Liet ke may ao (listvms)")
    raw(memu, "listvms")
    try:
        infos = memu.list2()
    except Exception:
        record(FAIL, "list2() hong:")
        traceback.print_exc()
        return 1
    if not infos:
        record(FAIL, "Khong phan tich duoc may ao nao -- dan output tho o tren de sua parser")
        return 1
    record(OK, f"Phan tich duoc {len(infos)} may ao")
    for i in infos:
        print(f"    index={i.index} name={i.name!r} chay={i.running} "
              f"hwnd={i.top_window_handle} pid={i.pid} cong_adb={memu.adb_port_for(i.index)}")

    # ------------------------------------------------------------------
    first = infos[0].index
    step(3, f"Doc cau hinh may ao index={first} (getconfigex)")
    for key in ("resolution_width", "resolution_height", "vbox_dpi",
                "is_customed_resolution", "cpus", "memory", "enable_su",
                "fps", "enable_audio", "imei", "macaddress"):
        raw(memu, "getconfigex", "-i", first, key)
    try:
        f = memu.find(first)
        if f and f.width and f.height:
            record(OK, f"find() doc duoc do phan giai {f.width}x{f.height}@{f.dpi}")
        else:
            record(WARN, f"find() khong ra do phan giai ({f}) -- xem output tho o tren")
    except Exception:
        record(FAIL, "find() hong:")
        traceback.print_exc()

    step(4, "Trang thai bat/tat (isvmrunning)")
    raw(memu, "isvmrunning", "-i", first)
    record(OK, f"is_running({first}) = {memu.is_running(first)} (doc tu listvms)")

    # ------------------------------------------------------------------
    if args.prepare is not None:
        idx = args.prepare
        step(5, f"Cau hinh may ao index={idx} cho flow (400x500 @160, root)")
        try:
            if memu.is_running(idx):
                print("  may ao dang chay -> tat truoc (doi cau hinh luc chay khong an)")
                memu.quit(idx)
                memu.wait_stopped(idx, settle=3)
            memu.modify(idx, width=400, height=500, dpi=160, root=True)
            record(OK, "da gui setconfigex")
        except Exception:
            record(FAIL, "modify() hong:")
            traceback.print_exc()
        else:
            # Doc LAI de chac setconfigex that su an -- memuc co the nhan khoa
            # sai ten ma khong bao loi gi.
            for key, want in (("resolution_width", "400"), ("resolution_height", "500"),
                              ("vbox_dpi", "160"), ("enable_su", "1"),
                              ("is_customed_resolution", "1")):
                got = memu.get_config(idx, key)
                record(OK if got == want else FAIL,
                       f"{key:24} = {got!r:8} (can {want!r})")
        if args.rename:
            try:
                memu.rename(idx, args.rename)
                ok = memu._find_fast(args.rename) is not None
                record(OK if ok else FAIL, f"doi ten -> {args.rename!r}")
            except Exception:
                record(FAIL, "rename hong:")
                traceback.print_exc()

    # ------------------------------------------------------------------
    if args.start is not None:
        idx = args.start
        step(6, f"Bat may ao index={idx} va doi Android boot")
        try:
            t0 = time.monotonic()
            memu.launch(idx)
            record(OK, "da goi memuc start")
            inst = Instance(memu, idx)
            print(f"  doi boot qua ADB tai {inst.serial} ...")
            inst.wait_boot_adb(timeout=240)
            record(OK, f"Android boot xong sau {time.monotonic() - t0:.0f}s")
        except Exception:
            record(FAIL, "launch / wait_boot_adb hong:")
            traceback.print_exc()
            port = memu.adb_port_for(idx)
            with socket.socket() as sk:
                sk.settimeout(0.5)
                opened = sk.connect_ex(("127.0.0.1", port)) == 0
            print(f"\n-> cong {port} {'DANG MO' if opened else 'DONG'}")
            print("   Neu dong: quy uoc 21503+10*index co the sai tren ban nay.")
            print(f'   Xem cong that: "{memu.adb_exe or "adb.exe"}" devices')
            return 1

        step(7, "Thu ADB that su goi duoc")
        try:
            record(OK, f"wm size -> {inst.sh('wm size').strip()!r}")
            record(OK, f"model  -> {inst.sh('getprop ro.product.model').strip()!r}")
        except Exception:
            record(FAIL, "shell hong:")
            traceback.print_exc()

        step(8, "Root -- can de lay cookie")
        form = inst._detect_su()
        if form == "none":
            record(WARN, "KHONG co root. Lay cookie se that bai.")
            print("   -> MEmu: Settings > Engine > Root mode, hoac:")
            print(f"      memuc setconfigex -i {idx} enable_su 1  roi khoi dong lai may ao")
        else:
            record(OK, f"co root, cu phap su kieu {'su 0 <lenh>' if form == '0' else 'su -c <lenh>'}")

    # ------------------------------------------------------------------
    if args.test_clone is not None:
        src = args.test_clone
        step(9, f"Thu clone index={src} -> _memu_check (roi xoa)")
        if memu.find("_memu_check"):
            print("  con sot _memu_check tu lan truoc -> xoa truoc")
            memu.remove("_memu_check")
        try:
            if memu.is_running(src):
                print("  may nguon dang chay -> tat truoc (clone o dia dang ghi = hong)")
                memu.quit(src)
                memu.wait_stopped(src)
            t0 = time.monotonic()
            memu.copy_from("_memu_check", src)
            new = memu.find("_memu_check")
            if new:
                record(OK, f"clone xong sau {time.monotonic() - t0:.0f}s -> index={new.index}")

                # Clone chep nguyen cau hinh -> ban clone mang Y HET dinh danh cua
                # may nguon. Farm doi bang `memuc randomize`; thu ngay tren ban
                # clone nay xem lenh do co that su doi gi khong.
                keys = ("imei", "macaddress")
                src_ids = {k: memu.get_config(src, k) for k in keys}
                cl_ids = {k: memu.get_config(new.index, k) for k in keys}
                same = all(src_ids[k] == cl_ids[k] for k in keys)
                record(OK if same else WARN,
                       f"clone {'mang y het' if same else 'KHAC'} dinh danh may nguon: {cl_ids}")

                out = raw(memu, "randomize", "-i", new.index)
                native = "LOI" not in out.upper() and "ERROR" not in out.upper()
                if not native:
                    print("  -> memuc khong co lenh randomize, thu nhanh du phong")
                    memu._randomize(new.index)
                after = {k: memu.get_config(new.index, k) for k in keys}
                changed = [k for k in keys if after[k] != cl_ids[k]]
                record(OK if len(changed) == len(keys) else FAIL,
                       f"{'memuc randomize' if native else 'nhanh du phong'} doi duoc "
                       f"{changed or 'KHONG GI'}: {after}")
                if not native:
                    record(WARN, "nhanh du phong KHONG doi duoc android_id -- cac clone "
                                 "co the bi gom nhom qua android_id")

                memu.remove("_memu_check")
                record(OK, "da xoa _memu_check")
            else:
                record(FAIL, "clone xong nhung khong thay _memu_check -- rename hong?")
        except Exception:
            record(FAIL, "clone hong:")
            traceback.print_exc()

    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    n_fail = sum(1 for s, _ in results if s == FAIL)
    n_warn = sum(1 for s, _ in results if s == WARN)
    print(f"KET QUA: {len(results) - n_fail - n_warn} OK, {n_warn} canh bao, {n_fail} loi")
    for s, m in results:
        if s != OK:
            print(f"  {s} {m}")
    print("=" * 60)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
