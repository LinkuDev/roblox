"""Nang adb.exe cua LDPlayer len ban moi cua Google.

LDPlayer ship kem adb 1.0.31 -- rat cu. No xu ly nhieu thiet bi dong thoi kem
han ban moi, hay tra ve 'device offline' hoac 'unknown data' khi bon may ao
cung goi mot luc. Ban 1.0.41 on hon nhieu.

Chi dung thu vien chuan (urllib, zipfile, subprocess) -- khong them dependency
nao vao exe, va chay duoc ca khi da dong goi bang PyInstaller.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

PLATFORM_TOOLS_URL = (
    "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
)
# adb.exe khong chay mot minh: thieu hai DLL nay la no im lang khong len server.
NEEDED = ("adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll")
# `adb version` in ra HAI so:
#     Android Debug Bridge version 1.0.41      <- version GIAO THUC
#     Version 35.0.2-12147458                  <- version platform-tools that
# So giao thuc dung yen o 1.0.41 tu nam 2017, nen no KHONG phan biet duoc ban
# nam 2019 voi ban nam nay. Phai doc them so thu hai moi biet ban co that su cu
# hay khong. LDPlayer ship ban 1.0.31 -- cu den muc so giao thuc cung khac.
MIN_VERSION = (1, 0, 41)
MIN_BUILD = (30, 0, 0)

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _run(cmd: list[str], timeout: float = 30) -> str:
    """Chay lenh, nuot loi. creationflags de khong nhay cua so den o app --windowed."""
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout,
                           creationflags=_CREATE_NO_WINDOW)
        return (p.stdout + p.stderr).decode("utf-8", "replace").strip()
    except Exception:
        return ""


def adb_version(adb: str | Path) -> tuple[int, ...] | None:
    """(1, 0, 41) hoac None neu khong doc duoc."""
    adb = Path(adb)
    if not adb.exists():
        return None
    m = re.search(r"version\s+(\d+)\.(\d+)\.(\d+)", _run([str(adb), "version"]))
    return tuple(int(g) for g in m.groups()) if m else None


def adb_build(adb: str | Path) -> tuple[int, ...] | None:
    """Version platform-tools that, vd (35, 0, 2). None neu ban qua cu (khong in)."""
    adb = Path(adb)
    if not adb.exists():
        return None
    m = re.search(r"^Version\s+(\d+)\.(\d+)\.(\d+)",
                  _run([str(adb), "version"]), re.M)
    return tuple(int(g) for g in m.groups()) if m else None


def version_str(v: tuple[int, ...] | None) -> str:
    return ".".join(map(str, v)) if v else "khong doc duoc"


def version_label(adb: str | Path) -> str:
    """Chuoi de hien cho nguoi dung, gom ca hai so."""
    proto, build = adb_version(adb), adb_build(adb)
    if proto is None:
        return "khong doc duoc"
    return f"{version_str(proto)}" + (f" (platform-tools {version_str(build)})"
                                      if build else " (khong ro platform-tools)")


def needs_upgrade(adb: str | Path) -> bool:
    """Co nen nang khong -- xet ca so giao thuc lan so platform-tools."""
    proto = adb_version(adb)
    if proto is None or proto < MIN_VERSION:
        return True
    build = adb_build(adb)
    # Khong in duoc so platform-tools = ban rat cu (truoc ~2017) -> nen nang.
    return build is None or build < MIN_BUILD


def find_bundled_adb() -> Path | None:
    """adb.exe di kem app, neu co.

    Ba cho tim, theo thu tu: canh exe (ban da giai nen ra, dung duoc lau dai),
    thu muc tam cua PyInstaller, va canh ma nguon khi chay bang python.
    Khong dung thang ban trong _MEIPASS de chay server: thu muc do bi xoa khi
    app thoat, ma adb server con song tiep -- se thanh tien trinh mo coi.
    """
    here = [Path(sys.executable).resolve().parent] if getattr(sys, "frozen", False) else []
    here.append(Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)))
    for base in here:
        for cand in (base / "adb" / "adb.exe", base / "adb.exe"):
            if cand.exists():
                return cand
    return None


def ensure_bundled_adb(dest_dir: str | Path) -> Path | None:
    """Chep adb di kem (trong _MEIPASS) ra `dest_dir` de dung lau dai.

    Tra ve duong dan adb.exe dung duoc, hoac None neu app khong di kem adb.
    """
    src = find_bundled_adb()
    if src is None:
        return None
    try:
        dest_dir = Path(dest_dir) / "adb"
        if src.parent == dest_dir:
            return src                  # da giai nen tu truoc
        # mkdir co the hong khi exe nam o cho chi doc (vd Program Files). Hong
        # o day khong duoc lam chet ca app: tra ve None de nguoi goi lui ve
        # adb cua LDPlayer.
        dest_dir.mkdir(parents=True, exist_ok=True)
        for name in NEEDED:
            f = src.parent / name
            if f.exists():
                try:
                    shutil.copy2(f, dest_dir / name)
                except OSError:
                    pass                # dang chay -> giu ban cu, van dung duoc
        out = dest_dir / "adb.exe"
        return out if out.exists() else None
    except OSError:
        return None


def download_platform_tools(log=print) -> Path:
    """Tai platform-tools cua Google, giai nen, tra ve thu muc chua adb.exe."""
    tmp = Path(tempfile.mkdtemp(prefix="pt_"))
    zip_path = tmp / "platform-tools.zip"
    log(f"tai {PLATFORM_TOOLS_URL} ...")
    with urllib.request.urlopen(PLATFORM_TOOLS_URL, timeout=120) as r, \
            open(zip_path, "wb") as f:
        shutil.copyfileobj(r, f)
    log(f"tai xong {zip_path.stat().st_size / 1e6:.1f} MB, dang giai nen...")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp)
    out = tmp / "platform-tools"
    if not (out / "adb.exe").exists():
        raise RuntimeError(f"Giai nen xong nhung khong thay adb.exe trong {out}")
    return out


def patch_ldplayer_adb(
    ld_dir: str | Path,
    log=print,
    kill_ldplayer: bool = True,
) -> tuple[bool, str]:
    """Thay adb.exe cua LDPlayer bang ban moi. Tra ve (thanh cong, mo ta).

    Khong chay khi farm dang chay: ham nay TAT LDPlayer va adb server, vi
    Windows khoa file dang chay nen khong ghi de duoc.
    """
    ld_dir = Path(ld_dir)
    if ld_dir.is_file():                 # lo truyen duong dan ldconsole.exe
        ld_dir = ld_dir.parent
    target = ld_dir / "adb.exe"
    if not target.exists():
        return False, f"Khong thay {target}"

    cur = version_label(target)
    log(f"adb hien tai: {cur}")
    if not needs_upgrade(target):
        return True, (f"adb da du moi ({cur}), khong can nang.\n\n"
                      f"Ban cu gay loi la 1.0.31 -- ban tren may nay moi hon.")

    try:
        src_dir = download_platform_tools(log)
    except Exception as exc:
        return False, f"Tai that bai: {type(exc).__name__}: {exc}"

    if kill_ldplayer:
        log("tat LDPlayer va adb server (file dang chay thi khong ghi de duoc)...")
        _run([str(target), "kill-server"], timeout=15)
        for name in ("dnplayer.exe", "dnconsole.exe", "adb.exe"):
            _run(["taskkill", "/F", "/IM", name], timeout=15)

    # Backup truoc khi ghi de: ban moi loi thi con duong lui.
    bak = ld_dir / "adb.exe.bak"
    if not bak.exists():
        try:
            shutil.copy2(target, bak)
            log(f"backup ban cu -> {bak.name}")
        except OSError as exc:
            log(f"khong backup duoc ({exc}) -- van tiep tuc")

    copied = []
    for name in NEEDED:
        f = src_dir / name
        if not f.exists():
            continue
        try:
            shutil.copy2(f, ld_dir / name)
            copied.append(name)
        except OSError as exc:
            return False, (f"Khong ghi duoc {name}: {exc}\n"
                           f"-> dong LDPlayer roi thu lai, hoac chay app bang "
                           f"quyen Administrator.")
    if "adb.exe" not in copied:
        return False, "Khong chep duoc adb.exe"

    new = version_label(target)
    log(f"adb sau khi nang: {new}")
    shutil.rmtree(src_dir.parent, ignore_errors=True)
    if not needs_upgrade(target):
        return True, f"Da nang adb: {cur} -> {new} ({', '.join(copied)})"
    return False, f"Chep xong nhung version doc ra van la {new}"


def _main() -> int:
    """python -m ldauto.adbsetup [thu_muc_LDPlayer]"""
    d = sys.argv[1] if len(sys.argv) > 1 else r"C:\LDPlayer\LDPlayer9"
    ok, msg = patch_ldplayer_adb(d)
    print(("[ OK ] " if ok else "[FAIL] ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_main())
