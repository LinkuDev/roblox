"""Gom moi thu can de chan doan vao mot file, de dan mot lan thay vi nam lan.

    python examples/collect_diag.py
    -> diag.txt
"""

import shutil
import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LD_DIR = Path(r"C:\LDPlayer\LDPlayer9")
LDCONSOLE = LD_DIR / "dnconsole.exe"
ADB = LD_DIR / "adb.exe"
OUT = Path("diag.txt")

_buf: list[str] = []


def w(line: str = "") -> None:
    print(line)
    _buf.append(line)


def run(*cmd: str, timeout: float = 60) -> str:
    try:
        p = subprocess.run([str(c) for c in cmd], capture_output=True, timeout=timeout)
        out = (p.stdout + p.stderr).decode("utf-8", "replace").strip()
        return f"(rc={p.returncode})\n{out}" if out else f"(rc={p.returncode}, khong in gi)"
    except Exception as exc:
        return f"<loi: {exc}>"


def section(title: str) -> None:
    w("\n" + "=" * 60)
    w(title)
    w("=" * 60)


def main() -> int:
    section("1. He thong")
    w(f"python: {sys.version.split()[0]}")
    total, used, free = shutil.disk_usage("C:\\")
    w(f"o C: trong {free / 1e9:.1f} GB / {total / 1e9:.1f} GB")

    section("2. Thu muc LDPlayer")
    for f in ("dnconsole.exe", "ldconsole.exe", "dnplayer.exe", "adb.exe"):
        w(f"  {f:16} {'co' if (LD_DIR / f).exists() else 'THIEU'}")

    section("3. list2")
    w(run(LDCONSOLE, "list2"))

    section("4. isrunning tung may ao")
    for idx in range(6):
        out = run(LDCONSOLE, "isrunning", "--index", str(idx), timeout=20)
        if "rc=0" in out:
            w(f"  index={idx}: {out.splitlines()[-1]!r}")

    section("5. Dung luong tung may ao")
    vms = LD_DIR / "vms"
    if vms.is_dir():
        for d in sorted(vms.iterdir()):
            if d.is_dir():
                size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                w(f"  {d.name:20} {size / 1e9:6.2f} GB")
    else:
        w(f"  khong thay {vms}")

    section("6. ADB")
    w(f"version: {run(ADB, 'version')}")
    w(f"devices: {run(ADB, 'devices', '-l')}")
    open_ports = []
    for port in range(5554, 5600):
        with socket.socket() as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                open_ports.append(port)
    w(f"cong dang mo: {open_ports}")

    section("7. Tung may ao qua ADB")
    for port in open_ports:
        serial = f"127.0.0.1:{port}"
        w(f"\n--- {serial} ---")
        run(ADB, "connect", serial, timeout=20)
        w(f"  wm size : {run(ADB, '-s', serial, 'shell', 'wm', 'size', timeout=20)}")
        # Loc chat: 'grep tun' bat ca tunl0/ip6tnl0 la interface mac dinh cua
        # Android, khong lien quan VPN. Chi tun0/tun1... moi la duong ham that.
        w(f"  tun     : {run(ADB, '-s', serial, 'shell', "ip -o addr | grep -E ' tun[0-9]'", timeout=20)}")
        w(f"  express : {run(ADB, '-s', serial, 'shell', 'pm list packages | grep -i express', timeout=20)}")
        w(f"  roblox  : {run(ADB, '-s', serial, 'shell', 'pm list packages | grep -i roblox', timeout=20)}")

    OUT.write_text("\n".join(_buf), encoding="utf-8")
    print(f"\n\n-> Da ghi {OUT.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
