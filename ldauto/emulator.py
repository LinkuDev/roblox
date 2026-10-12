"""Lop chung cho moi emulator Android dieu khien bang dong lenh.

Phan con lai cua thu vien (Instance, Farm, flow, GUI) chi noi chuyen voi lop
nay va khong can biet dang chay tren LDPlayer hay MEmu. Hai emulator khac nhau
o bon cho, va chi bon cho do:

  - chuong trinh dong lenh: ldconsole.exe / memuc.exe, cu phap khac han nhau
  - quy uoc cong ADB:       LDPlayer 5555 + 2*i,  MEmu 21503 + 10*i
  - cho de o dia may ao, ten tien trinh can tat, adb.exe di kem
  - setting nao ton tai (LDPlayer co global_setting/down_cpu, MEmu khong)

Phan dieu khien BEN TRONG Android (tap, swipe, chup man hinh, cookie) di qua
ADB nen giong het nhau tren moi emulator -- nam o instance.py, khong o day.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

# Emulator Trung Quoc in ra theo locale Windows chu khong phai utf-8.
# May Trung/Viet thuong la gbk hoac cp1258 -> decode cung utf-8 se no.
_ENCODINGS = ("utf-8", "gbk", "cp1252", "latin-1")


def _decode(raw: bytes) -> str:
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


class LDConsoleError(RuntimeError):
    """Lenh dong lenh cua emulator that bai. Ten giu nguyen cho code cu."""


EmulatorError = LDConsoleError


@dataclass
class InstanceInfo:
    """Mot may ao, doc tu lenh liet ke cua emulator."""

    index: int
    name: str
    top_window_handle: int
    bind_window_handle: int
    android_started: bool
    pid: int
    vbox_pid: int
    width: int | None = None
    height: int | None = None
    dpi: int | None = None
    # Emulator nao bao THANG trang thai bat/tat (MEmu co cot rieng) thi dien vao
    # day. None = suy tu pid nhu LDPlayer.
    state: bool | None = None

    @property
    def running(self) -> bool:
        if self.state is not None:
            return self.state
        # pid == -1 nghia la may ao chua bat.
        return self.pid not in (-1, 0)


class Emulator:
    """Mat chung cua moi emulator. Lop con cai dat phan danh dau BAT BUOC."""

    kind: str = "?"
    # Tien trinh can tat truoc khi ghi de adb.exe cua emulator.
    process_names: tuple[str, ...] = ("adb.exe",)

    # ---------- BAT BUOC: lop con phai cai dat ----------

    def adb_port_for(self, index: int) -> int:
        """Cong ADB cua may ao `index` theo quy uoc cua emulator nay."""
        raise NotImplementedError

    def list2(self) -> list[InstanceInfo]:
        """Moi may ao. Ten giu theo lenh LDPlayer cho code cu khoi doi."""
        raise NotImplementedError

    def launch(self, instance: int | str) -> None:
        raise NotImplementedError

    def quit(self, instance: int | str) -> None:
        raise NotImplementedError

    def quit_all(self) -> None:
        raise NotImplementedError

    def create(self, name: str) -> None:
        raise NotImplementedError

    def copy_from(self, name: str, source: int | str, **kw) -> None:
        raise NotImplementedError

    def remove(self, instance: int | str) -> None:
        raise NotImplementedError

    def rename(self, instance: int | str, new_name: str) -> None:
        raise NotImplementedError

    def modify(self, instance: int | str, **kw) -> None:
        raise NotImplementedError

    def run_app(self, instance: int | str, package: str) -> None:
        raise NotImplementedError

    def kill_app(self, instance: int | str, package: str) -> None:
        raise NotImplementedError

    def install_apk(self, instance: int | str, apk: str | Path) -> None:
        raise NotImplementedError

    def adb(self, instance: int | str, command: str, timeout: float | None = None) -> str:
        raise NotImplementedError

    # ---------- co san mac dinh ----------

    @property
    def adb_exe(self) -> Path | None:
        """adb.exe emulator ship kem, nam canh chuong trinh dong lenh."""
        cand = Path(self.path).parent / "adb.exe"
        return cand if cand.exists() else None

    @property
    def install_dir(self) -> Path:
        return Path(self.path).parent

    def find(self, instance: int | str) -> InstanceInfo | None:
        key = "index" if isinstance(instance, int) else "name"
        for info in self.list2():
            if getattr(info, key) == instance:
                return info
        return None

    def _find_fast(self, instance: int | str) -> InstanceInfo | None:
        """Nhu find() nhung khong can do phan giai.

        Dung cho nhung cho poll lien tuc (is_running, wait_stopped). Emulator
        nao phai ton them lenh moi lay duoc do phan giai thi ghi de cai nay.
        """
        return self.find(instance)

    def exists(self, name: str) -> bool:
        return self._find_fast(name) is not None

    def is_running(self, instance: int | str) -> bool:
        info = self._find_fast(instance)
        return info is not None and info.running

    def wait_stopped(
        self,
        instance: int | str,
        timeout: float = 60.0,
        poll: float = 1.0,
        settle: float = 8.0,
    ) -> None:
        """Doi may ao tat han. Lenh tat tra ve ngay, tien trinh con song them vai giay.

        pid bien mat VAN CHUA du: hypervisor giu file handle them mot luc, va
        lenh dung o dia trong khoang ay (copy/clone) that bai khong ly do.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            info = self._find_fast(instance)
            if info is None or not info.running:
                time.sleep(settle)
                return
            time.sleep(poll)
        raise TimeoutError(f"{instance} khong tat trong {timeout}s")

    def wait_boot(self, instance: int | str, timeout: float = 180.0, poll: float = 2.0) -> None:
        """Doi Android boot xong qua lenh adb cua emulator.

        Instance.wait_boot_adb hoi thang cong ADB va tin cay hon; giu ham nay
        cho cho nao can di qua emulator.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.adb(instance, "shell getprop sys.boot_completed",
                            timeout=15).strip().endswith("1"):
                    return
            except Exception:
                pass
            time.sleep(poll)
        raise TimeoutError(f"{instance} khong boot xong trong {timeout}s")

    def ensure_adb(self, indices=None, log=print) -> int:
        """Bat quyen truy cap ADB cho cac may ao `indices`. Tra ve so may da sua.

        Mac dinh khong lam gi: emulator nao ADB luon bat (MEmu -- da kiem tren
        may that) thi khong co gi de bat. Emulator nao co setting rieng thi ghi
        de ham nay. Goi luc may ao DANG TAT.
        """
        return 0

    def global_setting(self, **kw) -> None:
        """Setting chung cho ca emulator. Mac dinh: khong co gi de dat."""

    def down_cpu(self, instance: int | str, rate: int) -> None:
        """Gioi han CPU. Mac dinh: emulator khong ho tro thi bo qua."""

    def sort_windows(self) -> None:
        """Xep cua so. Mac dinh: khong lam gi."""

    def vm_dir(self, index: int) -> Path | None:
        """Thu muc o dia cua may ao, de do dung luong luc clone. None = khong biet."""
        return None

    @staticmethod
    def _dir_size(d: Path) -> int:
        try:
            return sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        except OSError:
            return 0


# Ten chuong trinh DONG LENH cua tung emulator. Cung thu muc con co chuong
# trinh GIAO DIEN (MEmu.exe, dnplayer.exe...). Chon nham file giao dien thi moi
# lenh mo cua so emulator ra roi dung im mai, toi khi het timeout 60s -- nhin
# tu ngoai giong het "emulator bat duoc nhung khong dieu khien duoc".
_CLI_NAMES = {
    "memu": ("memuc.exe",),
    "ldplayer": ("ldconsole.exe", "dnconsole.exe"),
}
_GUI_NAMES = {
    "memu.exe", "memuconsole.exe", "memuheadless.exe",
    "dnplayer.exe", "ldplayer.exe", "dnmultiplayer.exe", "ldmultiplayer.exe",
}


def resolve_cli(path: str | Path, kind: str | None = None) -> Path:
    """Duong dan toi chuong trinh DONG LENH, sua lai neu lo chon file giao dien.

    MEmu.exe -> memuc.exe, dnplayer.exe -> dnconsole.exe, cung thu muc. Dua ca
    thu muc cai dat cung duoc. Ten la thi tin nguoi dung, tra nguyen.
    """
    path = Path(path)
    kind = (kind or detect_kind(path)).lower()
    names = _CLI_NAMES.get(kind, ())
    if path.name.lower() in names:
        return path
    folder = path if path.is_dir() else path.parent
    for n in names:
        if (folder / n).exists():
            return folder / n
    if path.name.lower() in _GUI_NAMES:
        raise FileNotFoundError(
            f"{path.name} la chuong trinh GIAO DIEN cua emulator, khong dieu khien "
            f"duoc bang dong lenh. Can {' / '.join(names)} -- nhung khong thay "
            f"trong {folder}.")
    return path


def detect_kind(path: str | Path) -> str:
    """Doan emulator tu ten chuong trinh dong lenh: 'memu' hoac 'ldplayer'."""
    name = Path(path).name.lower()
    if name.startswith("memuc") or "memu" in str(path).lower():
        return "memu"
    return "ldplayer"


def open_emulator(
    path: str | Path,
    kind: str | None = None,
    timeout: float = 60.0,
) -> Emulator:
    """Mo dung lop emulator cho chuong trinh dong lenh `path`.

    Khong can chon tay: dua duong dan memuc.exe thi ra MEmu, dnconsole.exe /
    ldconsole.exe thi ra LDPlayer. `kind` de ep khi ten file khong theo quy uoc.
    """
    kind = (kind or detect_kind(path)).lower()
    path = resolve_cli(path, kind)
    if kind == "memu":
        from .memu import MemuConsole
        return MemuConsole(path, timeout=timeout)
    from .console import LDConsole
    return LDConsole(path, timeout=timeout)
