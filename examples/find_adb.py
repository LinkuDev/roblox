"""Do xem may ao LDPlayer that su nghe ADB o cong nao.

Quy uoc 5555+index*2 khong phai luc nao cung dung: doi trong settings, ban
LDPlayer khac, hay nhieu may ao bat theo thu tu khac deu lam lech.

    python examples/find_adb.py
"""

import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ADB = r"C:\LDPlayer\LDPlayer9\adb.exe"
PORT_RANGE = range(5554, 5600)


def port_open(port: int, timeout: float = 0.3) -> bool:
    with socket.socket() as s:
        s.settimeout(timeout)
        return s.connect_ex(("127.0.0.1", port)) == 0


def adb(*args: str, timeout: float = 15) -> str:
    try:
        p = subprocess.run([ADB, *args], capture_output=True, timeout=timeout)
        return (p.stdout + p.stderr).decode("utf-8", "replace").strip()
    except Exception as exc:
        return f"<loi: {exc}>"


def main() -> int:
    if not Path(ADB).exists():
        print(f"[FAIL] Khong thay {ADB}")
        return 1

    print("1. adb devices (truoc khi do)")
    print("   " + adb("devices").replace("\n", "\n   ") + "\n")

    print(f"2. Do cong {PORT_RANGE.start}-{PORT_RANGE.stop - 1}...")
    open_ports = [p for p in PORT_RANGE if port_open(p)]
    if not open_ports:
        print("   Khong cong nao mo.\n")
        print("-> ADB debugging dang TAT trong LDPlayer. Bat len:")
        print("   Settings > Other settings > ADB debugging > Open local connection")
        print("   roi KHOI DONG LAI may ao.")
        return 1
    print(f"   Cong dang mo: {open_ports}\n")

    print("3. Thu ket noi tung cong")
    found = []
    for p in open_ports:
        serial = f"127.0.0.1:{p}"
        print(f"\n   --- {serial} ---")
        print(f"   connect   : {adb('connect', serial)!r}")
        print(f"   get-state : {adb('-s', serial, 'get-state')!r}")
        print(f"   devices -l:")
        for line in adb("devices", "-l").splitlines()[1:]:
            if line.strip():
                print(f"       {line}")
        # In NGUYEN VAN loi thay vi nuot di -- day moi la thu can doc.
        size = adb("-s", serial, "shell", "wm", "size")
        print(f"   wm size   : {size!r}")
        if size and "error" not in size.lower() and "x" in size:
            found.append(serial)

    if not found:
        print("\n4. Khong goi duoc shell -> thu kill-server roi lam lai")
        print(f"   kill-server: {adb('kill-server')!r}")
        print(f"   start-server: {adb('start-server')!r}")
        for p in open_ports:
            serial = f"127.0.0.1:{p}"
            adb("connect", serial)
            size = adb("-s", serial, "shell", "wm", "size")
            print(f"   {serial} wm size: {size!r}")
            if size and "error" not in size.lower() and "x" in size:
                found.append(serial)

    print("\n5. Ket luan")
    if not found:
        print("   Van khong goi duoc shell.")
        print("   -> Kha nang cao nhat: ADB debugging trong LDPlayer dang TAT.")
        print("      Settings > Other settings > ADB debugging > Open local connection")
        print("      Luu lai roi KHOI DONG LAI may ao (khong phai chi dong cua so).")
        print("   -> Neu da bat roi ma van the: xem dong 'devices -l' o tren.")
        print("      'offline'      = may ao chua boot xong, doi them.")
        print("      'unauthorized' = co hop thoai 'Allow USB debugging' trong may ao, bam OK.")
        return 1

    for serial in found:
        port = int(serial.rsplit(":", 1)[1])
        idx = (port - 5555) // 2 if port >= 5555 and (port - 5555) % 2 == 0 else None
        if idx is not None:
            print(f"   {serial}  -> khop quy uoc, dung --index {idx}")
        else:
            print(f"   {serial}  -> LECH quy uoc, phai truyen tay --port {port}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
