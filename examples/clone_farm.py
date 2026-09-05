"""Nhan ban mot may ao DA CAI SAN app thanh nhieu ban giong het.

Khac setup_farm.py: khong tao may ao trang roi cai lai APK tung cai, ma copy
thang tu may ao nguon -- app da nam san trong image nen nhanh hon nhieu.

    python examples/clone_farm.py

Doi cac hang so o duoi cho khop may ban truoc khi chay.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ldauto import Farm, Instance, LDConsole, Spec  # noqa: E402

# --------------------------------------------------------------------------
LDCONSOLE = r"C:\LDPlayer\LDPlayer9\dnconsole.exe"
SOURCE = "roblox"       # may ao nguon, da cai san Roblox + ExpressVPN
PREFIX = "bot"          # clone se ten bot0, bot1, bot2...
COUNT = 3
CPU = 2
MEMORY = 2048
CPU_LIMIT = 60          # % CPU moi may ao, 0 = khong gioi han
START_AFTER_CLONE = True
STAGGER = 20            # giay giua moi lan bat, tranh dung CPU cung luc
# --------------------------------------------------------------------------


def main() -> int:
    console = LDConsole(LDCONSOLE)

    src = console.find(SOURCE)
    if src is None:
        print(f"[FAIL] Khong co may ao ten {SOURCE!r}. Dang co:")
        for i in console.list2():
            print(f"    index={i.index} name={i.name!r}")
        return 1

    # Lay resolution tu chinh may ao nguon, khong hardcode: clone phai giong het
    # nguon thi anh mau chup tren nguon moi dung tren clone.
    if src.width and src.height:
        spec = Spec(width=src.width, height=src.height, dpi=src.dpi or 240,
                    cpu=CPU, memory=MEMORY)
    else:
        print("[WARN] list2 khong tra ve resolution, dung mac dinh cua Spec")
        spec = Spec(cpu=CPU, memory=MEMORY)

    print(f"Nguon : index={src.index} name={src.name!r} "
          f"{spec.width}x{spec.height}@{spec.dpi}")
    print(f"Clone : {COUNT} ban -> {PREFIX}0..{PREFIX}{COUNT - 1}")
    print("Moi clone duoc randomize imei/mac/android_id de khong bi coi la cung mot may.\n")

    # Farm.ensure() tu tat may ao nguon truoc khi copy (copy o dia dang ghi =
    # image hong) va tu tat clone truoc khi doi resolution.
    farm = Farm(console)
    instances: list[Instance] = []
    for i in range(COUNT):
        name = f"{PREFIX}{i}"
        t0 = time.monotonic()
        print(f"[{name}] dang copy tu {SOURCE}... (vai GB, doi vai phut)")
        # index chu khong phai ten -- `copy --from` nhan index chac chan hon.
        inst = farm.ensure(name, spec, source=src.index)
        print(f"[{name}] xong sau {time.monotonic() - t0:.0f}s -> index={inst.index}")
        instances.append(inst)

    if not START_AFTER_CLONE:
        print("\nDa clone xong, khong bat theo yeu cau (START_AFTER_CLONE=False).")
        return 0

    print()
    for n, inst in enumerate(instances):
        if n:
            time.sleep(STAGGER)
        print(f"[index={inst.index}] dang bat, doi boot qua ADB...")
        try:
            # boot_via='adb' vi passthrough `dnconsole adb --command` khong dang tin
            # tren ban nay -- no de wait_boot() treo den het timeout.
            inst.start()
            print(f"[index={inst.index}] san sang -> {inst.serial}")
            if CPU_LIMIT:
                console.down_cpu(inst.index, CPU_LIMIT)
        except Exception as exc:
            print(f"[index={inst.index}] bat that bai: {exc}")

    print(f"\nADB dang thay: {Instance.list_adb_devices() or 'khong co gi'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
