"""Doc/sua file cau hinh tung may ao cua LDPlayer.

LDPlayer giu cau hinh moi may ao trong mot file JSON rieng:
    <LDPlayer>\\vms\\config\\leidian<N>.config

Thu can nhat o day la ADB debugging. No la setting CUA TUNG MAY AO chu khong
phai setting chung, nen may moi cai hay clone moi tao deu co the dang tat --
va luc do cong ADB van mo nhung bat tay khong bao gio xong, adb bao
'device offline' mai. Bat tay tung may qua giao dien thi qua cuc khi co chuc
may, nen sua thang file.

KHONG doan ten khoa: LDPlayer doi ten khoa giua cac phien ban. Tim theo mau
(khoa nao chua 'adb') roi bao lai nguoi dung thay vi hardcode mot cai ten.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

# 0 = tat, 1 = chi loopback, 2 = mo ra mang ngoai.
ADB_CLOSE, ADB_LOCAL, ADB_REMOTE = 0, 1, 2
_ADB_KEY = re.compile(r"adb", re.I)


def config_dir(ld_dir: str | Path) -> Path:
    ld_dir = Path(ld_dir)
    if ld_dir.is_file():                 # lo truyen duong dan ldconsole.exe
        ld_dir = ld_dir.parent
    return ld_dir / "vms" / "config"


def config_files(ld_dir: str | Path) -> list[Path]:
    d = config_dir(ld_dir)
    if not d.is_dir():
        return []
    # leidian.config la cau hinh MAC DINH cho may ao tao moi -- sua ca no thi
    # may clone sau nay khoi phai sua lai.
    return sorted(d.glob("leidian*.config"))


def read_adb_keys(path: str | Path) -> dict[str, object]:
    """Cac khoa lien quan adb trong mot file config."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {k: v for k, v in data.items() if _ADB_KEY.search(k)}


def survey(ld_dir: str | Path) -> list[tuple[str, dict[str, object]]]:
    """[(ten file, {khoa adb: gia tri})] -- de nhin xem dang bat hay tat."""
    return [(f.name, read_adb_keys(f)) for f in config_files(ld_dir)]


def set_adb_debug(
    ld_dir: str | Path,
    value: int = ADB_LOCAL,
    log=print,
) -> tuple[int, int]:
    """Bat ADB debugging cho MOI may ao. Tra ve (so file da sua, so file xem qua).

    May ao phai DANG TAT: LDPlayer giu cau hinh trong bo nho va ghi de luc
    thoat, sua trong khi no dang chay thi mat trang.
    """
    files = config_files(ld_dir)
    if not files:
        log(f"khong thay file config nao trong {config_dir(ld_dir)}")
        return 0, 0

    changed = 0
    for f in files:
        try:
            raw = f.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception as exc:
            log(f"  {f.name}: doc khong duoc ({type(exc).__name__}) -- bo qua")
            continue

        keys = [k for k in data if _ADB_KEY.search(k)]
        if not keys:
            # Khoa chua ton tai -> them khoa theo ten LDPlayer 9 dung. Neu ban
            # LDPlayer dung ten khac thi no se lo ra o lan survey sau.
            keys = ["basicSettings.adbDebug"]
            log(f"  {f.name}: chua co khoa adb -> them {keys[0]}")

        touched = False
        for k in keys:
            if data.get(k) != value:
                log(f"  {f.name}: {k} {data.get(k)!r} -> {value}")
                data[k] = value
                touched = True
        if not touched:
            continue

        bak = f.with_suffix(f.suffix + ".bak")
        if not bak.exists():
            try:
                shutil.copy2(f, bak)
            except OSError:
                pass
        try:
            f.write_text(json.dumps(data, indent=4, ensure_ascii=False),
                         encoding="utf-8")
            changed += 1
        except OSError as exc:
            log(f"  {f.name}: ghi khong duoc ({exc}) -- chay quyen Administrator?")

    return changed, len(files)


def _main() -> int:
    """python -m ldauto.ldconfig [thu_muc_LDPlayer] [--set]"""
    import sys

    d = sys.argv[1] if len(sys.argv) > 1 else r"C:\LDPlayer\LDPlayer9"
    if "--set" in sys.argv:
        n, total = set_adb_debug(d)
        print(f"Da sua {n}/{total} file. Khoi dong lai may ao de an.")
        return 0
    for name, keys in survey(d):
        print(f"{name}: {keys or '(khong co khoa adb nao)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
