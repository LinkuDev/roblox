"""Wrapper quanh ldconsole.exe cua LDPlayer 9.

Chi lo phan quan ly may ao: tao / sua cau hinh / bat / tat.
Phan dieu khien ben trong Android nam o instance.py.
"""

from __future__ import annotations

import csv
import subprocess
import warnings
import time
from dataclasses import dataclass
from pathlib import Path

# ldconsole in ra theo locale cua Windows, khong phai lu utf-8.
# May Trung/Viet thuong la gbk hoac cp1258 -> decode cung utf-8 se no.
_ENCODINGS = ("utf-8", "gbk", "cp1252", "latin-1")


def _decode(raw: bytes) -> str:
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


# AutoLDPlayer (LDPlayer.cs) ghi ro bo gia tri ldconsole nhan:
#   --cpu <1|2|3|4>   --memory <512|1024|2048|4096|8192>
# LD9 noi rong them vai muc, nen dung tap hop rong hon va chi CANH BAO.
# Gia tri la khong bao loi -- ldconsole bo qua trong im lang.
_MEMORY_CHOICES = {512, 1024, 1536, 2048, 3072, 4096, 6144, 8192}
_CPU_CHOICES = {1, 2, 3, 4, 6, 8}


class LDConsoleError(RuntimeError):
    pass


@dataclass
class InstanceInfo:
    """Mot dong cua `ldconsole list2`."""

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

    @property
    def running(self) -> bool:
        # pid == -1 nghia la may ao chua bat.
        return self.pid not in (-1, 0)


class LDConsole:
    def __init__(self, ldconsole: str | Path, timeout: float = 60.0):
        self.path = Path(ldconsole)
        if not self.path.exists():
            raise FileNotFoundError(f"Khong thay ldconsole.exe tai: {self.path}")
        self.timeout = timeout

    # ---------- lop nen ----------

    def run(self, *args: str, timeout: float | None = None) -> str:
        """Goi ldconsole va tra ve stdout da strip.

        Khong doan lo bang "stdout co rong khong" nhu mot so wrapper tren PyPI --
        nhieu lenh ldconsole van in text khi thanh cong. Chi tin returncode.
        """
        cmd = [str(self.path), *map(str, args)]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout or self.timeout,
            )
        except OSError as exc:
            # WinError 740 = "requires elevation". ldconsole.exe co manifest doi
            # quyen admin, nen goi tu terminal thuong chet ngay luc tao tien
            # trinh -- truoc ca khi chay duoc lenh nao. Loi goc khong he nhac
            # den admin nen rat de mat thoi gian di tim nham cho.
            if getattr(exc, "winerror", None) == 740:
                raise LDConsoleError(
                    f"{self.path.name} doi quyen Administrator.\n"
                    f"-> Mo cmd/PowerShell bang 'Run as administrator' roi chay lai."
                ) from exc
            raise
        out = _decode(proc.stdout).strip()
        err = _decode(proc.stderr).strip()
        if proc.returncode != 0:
            hint = ""
            if not out and not err:
                hint = ("\nldconsole khong in ly do. Thuong la: may ao nguon dang chay, "
                        "ten da ton tai, het dung luong o dia, hoac ten co ky tu la.")
            raise LDConsoleError(
                f"ldconsole {' '.join(map(str, args))} -> rc={proc.returncode}\n"
                f"stdout: {out}\nstderr: {err}{hint}"
            )
        return out

    @staticmethod
    def _target(instance: int | str) -> list[str]:
        """LDPlayer nhan dien may ao bang --index (so) hoac --name (chuoi)."""
        if isinstance(instance, int):
            return ["--index", str(instance)]
        return ["--name", instance]

    # ---------- liet ke ----------

    def list2(self) -> list[InstanceInfo]:
        """Danh sach day du. Dung CSV parser vi ten may ao co the chua dau phay/space."""
        raw = self.run("list2")
        infos: list[InstanceInfo] = []
        for row in csv.reader(raw.splitlines()):
            if len(row) < 7:
                continue
            nums = [int(x) if x.lstrip("-").isdigit() else -1 for x in row[2:]]
            infos.append(
                InstanceInfo(
                    index=int(row[0]),
                    name=row[1],
                    top_window_handle=nums[0],
                    bind_window_handle=nums[1],
                    android_started=bool(nums[2]),
                    pid=nums[3],
                    vbox_pid=nums[4],
                    width=nums[5] if len(nums) > 5 else None,
                    height=nums[6] if len(nums) > 6 else None,
                    dpi=nums[7] if len(nums) > 7 else None,
                )
            )
        return infos

    def find(self, instance: int | str) -> InstanceInfo | None:
        key = "index" if isinstance(instance, int) else "name"
        for info in self.list2():
            if getattr(info, key) == instance:
                return info
        return None

    def exists(self, name: str) -> bool:
        return self.find(name) is not None

    def is_running(self, instance: int | str) -> bool:
        """Doc pid tu list2 thay vi so chuoi tra ve cua lenh `isrunning`.

        (Ban dau doi cach nay vi nghi `isrunning` in tieng Trung tren ban TQ --
        do la SAI, no van in 'running'/'stop'. Nhung doc pid van tot hon: mot
        lenh it hon, va la so nen khong phu thuoc chuoi ldconsole in ra.)
        """
        info = self.find(instance)
        return info is not None and info.running

    # ---------- vong doi ----------

    def create(self, name: str) -> None:
        self.run("add", "--name", name)

    def copy_from(
        self,
        name: str,
        source: int | str,
        timeout: float = 1800.0,
        retries: int = 8,
        retry_delay: float = 30.0,
    ) -> None:
        """Nhan ban tu may ao co san -- nhanh hon `create` vi khoi cai lai app.

        LDPlayer chep o TIEN TRINH NEN: lenh nay tra ve gan nhu tuc thi (0s) roi
        van con chep tiep vai GB phia sau. Goi copy thu hai trong luc do bi tu
        choi bang rc=3, khong kem thong bao nao. Khong co lenh nao hoi duoc
        "chep xong chua", nen cach chac an la thu lai co cho.

        Lan thu that bai co the de lai mot clone hong dang do mang dung ten
        `name`; phai xoa truoc khi thu lai, neu khong lan sau se bao trung ten.
        Chi xoa duoc an toan vi `name` la ten clone moi -- Farm.ensure() da xac
        nhan no chua ton tai truoc khi goi vao day.
        """
        for attempt in range(retries + 1):
            try:
                self.run("copy", "--name", name, "--from", str(source), timeout=timeout)
                return
            except LDConsoleError as exc:
                if attempt >= retries:
                    raise
                # In NGUYEN VAN loi ldconsole tra ve. Truoc day cho nay in
                # "LDPlayer dang ban" -- do la phong doan cua minh chu khong
                # phai dieu ldconsole noi, va no che mat ma loi that.
                first = str(exc).splitlines()[0]
                print(f"  [{name}] thu {attempt + 1}/{retries} that bai: {first}")

                # Doi TRUOC khi xoa: neu ldconsole dang chep o tien trinh nen
                # thi xoa ngay se dam vao giua chung. Doi xong ma may ao da
                # hien ra day du thi coi nhu no chep xong that.
                time.sleep(retry_delay)
                leftover = self.find(name)
                if leftover is not None:
                    if leftover.width:
                        print(f"  [{name}] da co may ao ({leftover.width}x{leftover.height}) "
                              f"-> coi nhu copy da xong o tien trinh nen")
                        return
                    print(f"  [{name}] con lai ban hong dang do -> xoa roi thu lai")
                    self.remove(name)

    def remove(self, instance: int | str) -> None:
        self.run("remove", *self._target(instance))

    def launch(self, instance: int | str) -> None:
        if self.is_running(instance):
            return
        self.run("launch", *self._target(instance))

    def launch_app(self, instance: int | str, package: str) -> None:
        """Bat may ao VA mo app trong mot lenh (launchex).

        Tien hon launch() roi run_app() vi khoi phai tu doi Android boot xong.
        """
        self.run("launchex", *self._target(instance), "--packagename", package)

    def quit(self, instance: int | str) -> None:
        self.run("quit", *self._target(instance))

    def quit_all(self) -> None:
        self.run("quitall")

    def wait_stopped(
        self,
        instance: int | str,
        timeout: float = 60.0,
        poll: float = 1.0,
        settle: float = 8.0,
    ) -> None:
        """Doi may ao tat han. `quit` tra ve ngay, tien trinh con song them vai giay.

        pid bien mat khoi list2 VAN CHUA du: VBox giu file handle them mot luc,
        va lenh dung o dia trong khoang ay (copy) that bai khong ly do.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            info = self.find(instance)
            if info is None or not info.running:
                time.sleep(settle)
                return
            time.sleep(poll)
        raise TimeoutError(f"{instance} khong tat trong {timeout}s")

    def reboot(self, instance: int | str) -> None:
        self.run("reboot", *self._target(instance))

    # ---------- cau hinh ----------

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
        """Doi cau hinh may ao.

        LUU Y: doi resolution khi may ao DANG CHAY se khong co tac dung
        cho toi lan khoi dong lai. Goi ham nay luc may ao dang tat.
        """
        # LDPlayer chi chap nhan mot so gia tri roi rac; gia tri la se bi lam tron
        # hoac bo qua trong im lang. Canh bao chu khong chan, vi bo gia tri
        # thay doi theo phien ban LDPlayer.
        if memory is not None and memory not in _MEMORY_CHOICES:
            warnings.warn(
                f"memory={memory} khong nam trong {sorted(_MEMORY_CHOICES)}; "
                "LDPlayer co the bo qua gia tri nay",
                stacklevel=2,
            )
        if cpu is not None and cpu not in _CPU_CHOICES:
            warnings.warn(
                f"cpu={cpu} khong nam trong {sorted(_CPU_CHOICES)}; "
                "LDPlayer co the bo qua gia tri nay",
                stacklevel=2,
            )

        args = ["modify", *self._target(instance)]
        if width and height:
            args += ["--resolution", f"{width},{height},{dpi}"]
        if cpu is not None:
            args += ["--cpu", str(cpu)]
        if memory is not None:
            args += ["--memory", str(memory)]
        if manufacturer:
            args += ["--manufacturer", manufacturer]
        if model:
            args += ["--model", model]
        if imei:
            args += ["--imei", imei]
        if mac:
            args += ["--mac", mac]
        if android_id:
            args += ["--androidid", android_id]
        if imsi:
            args += ["--imsi", imsi]
        if sim_serial:
            args += ["--simserial", sim_serial]
        if phone_number:
            args += ["--pnumber", phone_number]
        if lock_window is not None:
            args += ["--lockwindow", "1" if lock_window else "0"]
        if autorotate is not None:
            args += ["--autorotate", "1" if autorotate else "0"]
        if root is not None:
            args += ["--root", "1" if root else "0"]
        if len(args) == 3:
            raise ValueError("modify() duoc goi ma khong co tham so nao de doi")
        self.run(*args)

    def global_setting(
        self,
        *,
        fps: int | None = None,
        audio: bool | None = None,
        fast_play: bool | None = None,
        clean_mode: bool | None = None,
    ) -> None:
        args = ["globalsetting"]
        if fps is not None:
            args += ["--fps", str(fps)]
        if audio is not None:
            args += ["--audio", "1" if audio else "0"]
        if fast_play is not None:
            args += ["--fastplay", "1" if fast_play else "0"]
        if clean_mode is not None:
            args += ["--cleanmode", "1" if clean_mode else "0"]
        self.run(*args)

    def down_cpu(self, instance: int | str, rate: int) -> None:
        """Gioi han CPU (0-100). Huu ich khi chay nhieu may ao song song."""
        self.run("downcpu", *self._target(instance), "--rate", str(rate))

    # ---------- app ----------

    def running_list(self) -> list[str]:
        """Ten cac may ao dang chay. list2() cho nhieu thong tin hon,
        nhung lenh nay nhanh hon khi chi can biet may nao dang bat."""
        return [x for x in self.run("runninglist").splitlines() if x.strip()]

    def install_apk(self, instance: int | str, apk: str | Path) -> None:
        self.run("installapp", *self._target(instance), "--filename", str(apk), timeout=300)

    def install_from_store(self, instance: int | str, package: str) -> None:
        """Cai app theo package name (tai tu store trong may ao)."""
        self.run("installapp", *self._target(instance), "--packagename", package, timeout=600)

    def backup_app(self, instance: int | str, package: str, file: str | Path) -> None:
        self.run("backupapp", *self._target(instance), "--packagename", package,
                 "--file", str(file), timeout=600)

    def restore_app(self, instance: int | str, package: str, file: str | Path) -> None:
        self.run("restoreapp", *self._target(instance), "--packagename", package,
                 "--file", str(file), timeout=600)

    def uninstall(self, instance: int | str, package: str) -> None:
        self.run("uninstallapp", *self._target(instance), "--packagename", package)

    def run_app(self, instance: int | str, package: str) -> None:
        self.run("runapp", *self._target(instance), "--packagename", package)

    def kill_app(self, instance: int | str, package: str) -> None:
        self.run("killapp", *self._target(instance), "--packagename", package)


    def rename(self, instance: int | str, new_name: str) -> None:
        self.run("rename", *self._target(instance), "--title", new_name)

    def set_prop(self, instance: int | str, key: str, value: str) -> None:
        self.run("setprop", *self._target(instance), "--key", key, "--value", value)

    def get_prop(self, instance: int | str, key: str) -> str:
        return self.run("getprop", *self._target(instance), "--key", key)

    def action(self, instance: int | str, key: str, value: str) -> None:
        """Gui thao tac cap may ao, vd key="call.exit", "call.capture", "call.shake"."""
        self.run("action", *self._target(instance), "--key", key, "--value", value)

    def locate(self, instance: int | str, lng: float, lat: float) -> None:
        """Gia lap toa do GPS."""
        self.run("locate", *self._target(instance), "--LLI", f"{lng},{lat}")

    def backup(self, instance: int | str, file: str | Path) -> None:
        self.run("backup", *self._target(instance), "--file", str(file), timeout=1800)

    def restore(self, instance: int | str, file: str | Path) -> None:
        self.run("restore", *self._target(instance), "--file", str(file), timeout=1800)

    def push(self, instance: int | str, local: str | Path, remote: str) -> None:
        self.run("push", *self._target(instance), "--local", str(local), "--remote", remote)

    def pull(self, instance: int | str, remote: str, local: str | Path) -> None:
        self.run("pull", *self._target(instance), "--remote", remote, "--local", str(local))

    def send_image(self, instance: int | str, file: str | Path) -> None:
        """Day mot anh vao thu vien anh cua may ao (scan)."""
        self.run("scan", *self._target(instance), "--file", str(file))

    def zoom_in(self, instance: int | str) -> None:
        self.run("zoomIn", *self._target(instance))

    def zoom_out(self, instance: int | str) -> None:
        self.run("zoomOut", *self._target(instance))

    def sort_windows(self) -> None:
        """Xep lai cua so cac may ao thanh luoi -- tien khi chay nhieu instance."""
        self.run("sortWnd")

    # ---------- adb passthrough ----------

    def adb(self, instance: int | str, command: str, timeout: float | None = None) -> str:
        """Chay lenh adb qua ldconsole -- khoi phai tu doan cong adb."""
        return self.run("adb", *self._target(instance), "--command", command, timeout=timeout)

    def wait_boot(self, instance: int | str, timeout: float = 180.0, poll: float = 2.0) -> None:
        """Doi Android boot xong that su.

        `isrunning` chi bao cua so may ao da mo, chua chac Android da san sang.
        Moc dung la sys.boot_completed == 1.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.adb(instance, "shell getprop sys.boot_completed", timeout=15).strip() == "1":
                    return
            except (LDConsoleError, subprocess.TimeoutExpired):
                pass  # adb chua len, thu lai
            time.sleep(poll)
        raise TimeoutError(f"{instance} khong boot xong trong {timeout}s")
