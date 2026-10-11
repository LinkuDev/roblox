"""Wrapper quanh memuc.exe cua MEmu Play.

Cung mat voi LDConsole (xem emulator.py) nen Instance / Farm / flow dung duoc
nguyen xi. Khac LDPlayer o nhung cho sau, va day la nhung cho de vap:

  - Cong ADB: 21503 + 10*i  (MEmu_0 -> 21503, MEmu_1 -> 21513, ...)
  - `memuc` tra ve rc=0 KE CA KHI LOI, chi in "ERROR: ..." ra stdout -> phai
    doc chu chu khong tin returncode.
  - `listvms` khong co do phan giai. Phai hoi rieng tung khoa bang getconfigex,
    moi khoa mot tien trinh -- nen chi hoi khi that su can (find), khong hoi
    trong cac vong poll (is_running, wait_stopped).
  - `clone` khong cho dat ten: tao ra may ao moi ten tu dat, phai so danh sach
    truoc/sau de biet index moi roi rename.
  - Khong co global setting nhu LDPlayer: fps/audio dat theo TUNG may ao.
  - ADB luon bat san, khong co setting "ADB debugging" nhu LDPlayer.

Da kiem chung tren may that (examples/memu_check.py):
    doc     listvms (ca luc tat lan luc chay), getconfigex, isvmrunning
    ghi     setconfigex (do phan giai, dpi, root), rename
    chay    start -> Android boot -> ADB o 21503 (dung quy uoc) -> wm size 400x500
    root    `su 0 <lenh>` (giong LDPlayer; nhanh `su -c` de cho ban MEmu khac)
    clone   tat nguon -> clone -> tim index moi bang so danh sach -> rename
            -> vm_dir "MemuHyperv VMs\MEmu_<i>" dung -> remove
    khoa    fps, enable_audio dung ten: chi co gia tri SAU lan boot dau tien,
            truoc do memuc tra "No value set!"
CHUA kiem chung: randomize, installapp, startapp/stopapp.

Dinh dang that do duoc:
    listvms        0,MEmu,0,0,0                  (tat)
                   0,roblox,105251468,1,55832    (chay: hwnd, 1, pid)
    getconfigex    Value: 1280  |  Value: "327A..."  |  No value set!
                   (macaddress co ngoac kep truoc lan boot dau, mat ngoac sau do)
    isvmrunning    Not Running
"""

from __future__ import annotations

import csv
import random
import re
import subprocess
import sys
import time
from pathlib import Path

from .emulator import Emulator, InstanceInfo, LDConsoleError, _decode

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Khoa cau hinh cua memuc setconfigex / getconfigex.
_K_CUSTOM_RES = "is_customed_resolution"
_K_WIDTH = "resolution_width"
_K_HEIGHT = "resolution_height"
_K_DPI = "vbox_dpi"
_K_CPU = "cpus"
_K_MEMORY = "memory"
_K_ROOT = "enable_su"
_K_FPS = "fps"
_K_AUDIO = "enable_audio"
_K_IMEI = "imei"
_K_IMSI = "imsi"
_K_SIM = "simserial"
_K_PHONE = "linenum"
_K_MAC = "macaddress"
_K_BRAND = "microvirt_vm_brand"
_K_MODEL = "microvirt_vm_model"
_K_MANUFACTURER = "microvirt_vm_manufacturer"


def _int(s: str, default: int = -1) -> int:
    s = (s or "").strip()
    return int(s) if s.lstrip("-").isdigit() else default


def _luhn_imei() -> str:
    """IMEI 15 so hop le (so cuoi la so kiem tra Luhn).

    IMEI ngau nhien khong qua Luhn thi mot so app coi la gia ngay.
    """
    body = [random.randint(0, 9) for _ in range(14)]
    total = 0
    for i, d in enumerate(body):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return "".join(map(str, body)) + str((10 - total % 10) % 10)


def _random_mac() -> str:
    # Bit thu hai cua byte dau = 1: dia chi "locally administered", khong dung
    # hang voi card mang that cua hang nao.
    first = (random.randint(0, 255) & 0xFC) | 0x02
    rest = [random.randint(0, 255) for _ in range(5)]
    return "".join(f"{b:02X}" for b in [first, *rest])


class MemuConsole(Emulator):
    kind = "memu"
    process_names = ("MEmu.exe", "MEmuHeadless.exe", "MEmuConsole.exe",
                     "memuc.exe", "adb.exe")

    def __init__(self, memuc: str | Path, timeout: float = 60.0):
        self.path = Path(memuc)
        if not self.path.exists():
            raise FileNotFoundError(
                f"Khong thay memuc.exe tai: {self.path}\n"
                r"Thuong o: C:\Program Files\Microvirt\MEmu\memuc.exe")
        self.timeout = timeout

    def adb_port_for(self, index: int) -> int:
        return 21503 + index * 10

    # ---------- lop nen ----------

    @staticmethod
    def _looks_error(out: str) -> bool:
        """memuc bao loi bang chu chu khong bang returncode."""
        return any(line.strip().upper().startswith(("ERROR", "FAILED"))
                   for line in out.splitlines())

    def run(self, *args: str, timeout: float | None = None) -> str:
        cmd = [str(self.path), *map(str, args)]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout or self.timeout,
                # memuc tim cac DLL va file cau hinh theo thu muc hien tai.
                cwd=str(self.path.parent),
                creationflags=_CREATE_NO_WINDOW,
            )
        except OSError as exc:
            if getattr(exc, "winerror", None) == 740:
                raise LDConsoleError(
                    f"{self.path.name} doi quyen Administrator.\n"
                    f"-> Mo bang 'Run as administrator' roi chay lai."
                ) from exc
            raise
        out = _decode(proc.stdout).strip()
        err = _decode(proc.stderr).strip()
        if proc.returncode != 0 or self._looks_error(out):
            raise LDConsoleError(
                f"memuc {' '.join(map(str, args))} -> rc={proc.returncode}\n"
                f"stdout: {out}\nstderr: {err}"
            )
        return out

    def _idx(self, instance: int | str) -> int:
        """Doi ten -> index. Moi lenh deu dung `-i <index>` cho mot duong duy nhat."""
        if isinstance(instance, int):
            return instance
        info = self._find_fast(instance)
        if info is None:
            raise LDConsoleError(f"Khong co may ao MEmu ten {instance!r}")
        return info.index

    # ---------- liet ke ----------

    def list2(self) -> list[InstanceInfo]:
        """`memuc listvms`: index,title,hwnd,dang_chay,pid,dung_luong.

        KHONG kem do phan giai -- listvms khong co. Can thi goi find().
        """
        raw = self.run("listvms")
        infos: list[InstanceInfo] = []
        for row in csv.reader(raw.splitlines()):
            if len(row) < 4 or not row[0].strip().isdigit():
                continue                    # dong tieu de / dong rong / thong bao
            on = _int(row[3], 0) == 1
            pid = _int(row[4]) if len(row) > 4 else -1
            infos.append(InstanceInfo(
                index=int(row[0]),
                name=row[1].strip(),
                top_window_handle=_int(row[2], 0),
                bind_window_handle=0,
                android_started=on,
                pid=pid if on else -1,
                vbox_pid=-1,
                state=on,
            ))
        return infos

    def _find_fast(self, instance: int | str) -> InstanceInfo | None:
        key = "index" if isinstance(instance, int) else "name"
        for info in self.list2():
            if getattr(info, key) == instance:
                return info
        return None

    def get_config(self, instance: int | str, key: str) -> str:
        """Gia tri mot khoa cau hinh, "" neu chua dat.

        Output that cua memuc (do tren may that):
            Value: 1280
            Value: "327A4B9BEF53"      <- mot so khoa co ngoac kep
            No value set!              <- khoa chua dat, KHONG phai loi
        """
        out = self.run("getconfigex", "-i", self._idx(instance), key)
        last = out.strip().splitlines()[-1].strip() if out.strip() else ""
        if not last.lower().startswith("value:"):
            return ""                       # "No value set!" va moi thu khac
        return last.split(":", 1)[1].strip().strip('"')

    def _cfg_int(self, index: int, key: str) -> int | None:
        try:
            m = re.search(r"-?\d+", self.get_config(index, key))
            return int(m.group()) if m else None
        except LDConsoleError:
            return None

    def find(self, instance: int | str) -> InstanceInfo | None:
        """Nhu list2 nhung DIEN THEM do phan giai cho dung may ao can tim.

        Ton them ba tien trinh memuc, nen khong dung cai nay trong vong poll --
        cac cho do da di qua _find_fast.
        """
        info = self._find_fast(instance)
        if info is not None and info.width is None:
            info.width = self._cfg_int(info.index, _K_WIDTH)
            info.height = self._cfg_int(info.index, _K_HEIGHT)
            info.dpi = self._cfg_int(info.index, _K_DPI)
        return info

    # ---------- vong doi ----------

    def launch(self, instance: int | str) -> None:
        if self.is_running(instance):
            return
        # memuc start co the doi toi khi cua so hien ra -> cho timeout rong.
        self.run("start", "-i", self._idx(instance), timeout=180)

    def quit(self, instance: int | str) -> None:
        self.run("stop", "-i", self._idx(instance), timeout=120)

    def quit_all(self) -> None:
        self.run("stopall", timeout=180)

    def reboot(self, instance: int | str) -> None:
        self.run("reboot", "-i", self._idx(instance), timeout=180)

    def remove(self, instance: int | str) -> None:
        self.run("remove", "-i", self._idx(instance), timeout=300)

    def rename(self, instance: int | str, new_name: str) -> None:
        self.run("rename", "-i", self._idx(instance), new_name)

    def _wait_new_index(self, before: set[int], timeout: float) -> int:
        """Doi mot index chua co trong `before` hien ra trong listvms."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            new = sorted({i.index for i in self.list2()} - before)
            if new:
                return new[-1]
            time.sleep(3)
        raise LDConsoleError(f"khong thay may ao moi sau {timeout}s")

    def create(self, name: str) -> None:
        before = {i.index for i in self.list2()}
        self.run("create", timeout=600)
        self.rename(self._wait_new_index(before, 120), name)

    def copy_from(
        self,
        name: str,
        source: int | str,
        timeout: float = 1800.0,
        appear_timeout: float = 120.0,
        settle_timeout: float = 1800.0,
    ) -> None:
        """Nhan ban may ao `source` roi dat ten `name`.

        `memuc clone` KHONG cho dat ten: may ao moi tu lay ten rieng. Nen so
        danh sach index truoc va sau de biet may nao vua sinh ra, roi rename.

        Nhu LDConsole.copy_from, khong tin ma tra ve cua lenh clone -- xac nhan
        bang thu nhin thay duoc: may ao moi co hien ra khong, va o dia cua no
        da ngung phinh chua.
        """
        src = self._idx(source)
        before = {i.index for i in self.list2()}
        rc_error: LDConsoleError | None = None
        try:
            self.run("clone", "-i", src, timeout=timeout)
        except LDConsoleError as exc:
            rc_error = exc

        try:
            new_idx = self._wait_new_index(before, appear_timeout)
        except LDConsoleError:
            raise rc_error or LDConsoleError(
                f"clone {name} tu {source}: khong thay may ao moi sau {appear_timeout}s")
        if rc_error:
            print(f"  [{name}] memuc bao loi nhung may ao da tao duoc "
                  f"-> di tiep ({str(rc_error).splitlines()[0]})")

        self.rename(new_idx, name)

        d = self.vm_dir(new_idx)
        if d is None:
            return
        last, stable = -1, 0
        deadline = time.monotonic() + settle_timeout
        while time.monotonic() < deadline:
            size = self._dir_size(d)
            stable = stable + 1 if size == last and size > 0 else 0
            if stable >= 2:
                print(f"  [{name}] chep xong {size / 1e9:.2f} GB")
                return
            last = size
            time.sleep(5)
        print(f"  [{name}] thu muc van con phinh sau {settle_timeout:.0f}s -- di tiep")

    def vm_dir(self, index: int) -> Path | None:
        # May ao dau tien ten "MEmu", cac may sau "MEmu_<i>".
        base = self.path.parent / "MemuHyperv VMs"
        d = base / ("MEmu" if index == 0 else f"MEmu_{index}")
        return d if d.is_dir() else None

    # ---------- cau hinh ----------

    def set_config(self, instance: int | str, key: str, value) -> None:
        self.run("setconfigex", "-i", self._idx(instance), key, str(value))

    def _randomize(self, index: int) -> None:
        """Doi IMEI/MAC/android_id. Uu tien lenh co san cua memuc.

        Khong co lenh do (ban cu) thi tu sinh IMEI hop le Luhn va MAC
        "locally administered" roi dat tay.
        """
        try:
            self.run("randomize", "-i", index)
            return
        except LDConsoleError:
            pass
        self.set_config(index, _K_IMEI, _luhn_imei())
        self.set_config(index, _K_MAC, _random_mac())

    def modify(
        self,
        instance: int | str,
        *,
        width: int | None = None,
        height: int | None = None,
        dpi: int = 240,
        cpu: int | None = None,
        memory: int | None = None,
        manufacturer: str | None = None,
        model: str | None = None,
        imei: str | None = None,
        mac: str | None = None,
        android_id: str | None = None,
        imsi: str | None = None,
        sim_serial: str | None = None,
        phone_number: str | None = None,
        autorotate: bool | None = None,
        lock_window: bool | None = None,
        root: bool | None = None,
    ) -> None:
        """Doi cau hinh. Cung tham so voi LDConsole.modify de Farm dung chung.

        Goi luc may ao dang TAT: doi luc dang chay thi chi an o lan bat sau.
        autorotate / lock_window khong co tren MEmu -- bo qua.
        """
        i = self._idx(instance)
        sets: list[tuple[str, object]] = []
        if width and height:
            sets += [(_K_CUSTOM_RES, 1), (_K_WIDTH, width),
                     (_K_HEIGHT, height), (_K_DPI, dpi)]
        if cpu is not None:
            sets.append((_K_CPU, cpu))
        if memory is not None:
            sets.append((_K_MEMORY, memory))
        if manufacturer:
            sets.append((_K_MANUFACTURER, manufacturer))
        if model:
            sets.append((_K_MODEL, model))
        if root is not None:
            sets.append((_K_ROOT, 1 if root else 0))
        if imsi:
            sets.append((_K_IMSI, imsi))
        if sim_serial:
            sets.append((_K_SIM, sim_serial))
        if phone_number:
            sets.append((_K_PHONE, phone_number))
        # "auto" = LDPlayer tu sinh. MEmu khong hieu chu do -> tu randomize.
        if imei and imei != "auto":
            sets.append((_K_IMEI, imei))
        if mac and mac != "auto":
            sets.append((_K_MAC, mac))
        wants_random = "auto" in (imei, mac, android_id)
        if not sets and not wants_random:
            raise ValueError("modify() duoc goi ma khong co tham so nao de doi")

        for key, value in sets:
            self.set_config(i, key, value)
        if wants_random:
            self._randomize(i)

    def global_setting(
        self,
        *,
        fps: int | None = None,
        audio: bool | None = None,
        fast_play: bool | None = None,
        clean_mode: bool | None = None,
    ) -> None:
        """MEmu khong co setting chung: dat fps/audio cho TUNG may ao.

        fast_play / clean_mode chi LDPlayer co -- bo qua. Loi o mot may khong
        lam hong ca ham: day la toi uu, khong phai dieu kien de chay.
        """
        for info in self.list2():
            for key, value in ((_K_FPS, fps),
                               (_K_AUDIO, None if audio is None else int(audio))):
                if value is None:
                    continue
                try:
                    self.set_config(info.index, key, value)
                except LDConsoleError:
                    pass

    def sort_windows(self) -> None:
        self.run("sortwin")

    # ---------- app ----------

    def install_apk(self, instance: int | str, apk: str | Path) -> None:
        self.run("installapp", "-i", self._idx(instance), str(apk), timeout=300)

    def uninstall(self, instance: int | str, package: str) -> None:
        self.run("uninstallapp", "-i", self._idx(instance), package, timeout=120)

    def run_app(self, instance: int | str, package: str) -> None:
        self.run("startapp", "-i", self._idx(instance), package)

    def kill_app(self, instance: int | str, package: str) -> None:
        self.run("stopapp", "-i", self._idx(instance), package)

    # ---------- adb passthrough ----------

    def adb(self, instance: int | str, command: str, timeout: float | None = None) -> str:
        return self.run("adb", "-i", self._idx(instance), command, timeout=timeout)
