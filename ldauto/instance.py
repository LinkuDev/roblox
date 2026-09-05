"""Dieu khien ben trong mot may ao: tap, swipe, chup man hinh, tim anh."""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import adbutils
import cv2
import numpy as np

from .console import LDConsole


class Instance:
    """Gan mot may ao LDPlayer voi mot ket noi ADB."""

    def __init__(self, console: LDConsole, index: int, adb_port: int | None = None):
        self.console = console
        self.index = index
        # LDPlayer map index -> cong adb theo quy uoc: 0->5555, 1->5557, 2->5559...
        # Quy uoc nay co the sai neu ban da doi cong trong settings, nen cho phep ghi de.
        self.adb_port = adb_port if adb_port is not None else 5555 + index * 2
        self._device: adbutils.AdbDevice | None = None
        self._resolution: tuple[int, int] | None = None

    @property
    def serial(self) -> str:
        return f"127.0.0.1:{self.adb_port}"

    # ---------- ket noi ----------

    def connect(self, retries: int = 10, delay: float = 2.0) -> adbutils.AdbDevice:
        """Ket noi ADB, thu lai vi may ao vua boot thuong chua mo cong ngay."""
        last: Exception | None = None
        for _ in range(retries):
            try:
                adbutils.adb.connect(self.serial, timeout=5.0)
                dev = adbutils.adb.device(self.serial)
                dev.shell("echo ping")  # xac nhan that su goi duoc
                self._device = dev
                return dev
            except Exception as exc:  # adbutils nem nhieu loai loi khac nhau
                last = exc
                time.sleep(delay)
        raise ConnectionError(f"Khong ket noi duoc ADB toi {self.serial}: {last}")

    @property
    def device(self) -> adbutils.AdbDevice:
        if self._device is None:
            return self.connect()
        return self._device

    # Loi ADB thuoc nhom "ket noi rot", khac han loi that su cua lenh. Bat theo
    # chuoi vi adbutils nem chung mot class AdbError cho moi thu.
    _TRANSIENT = (
        "device not found",
        "offline",
        "unknown data",          # adb server dong ket noi giua chung
        "connection reset",
        "broken pipe",
        "cannot connect",
        "device still connecting",
        "closed",
    )

    def _retry(self, fn, *a, retries: int = 2, **kw):
        """Goi fn(device, ...), noi lai neu ket noi rot.

        LDPlayer tha ket noi ADB giua chung, va ban adb no ship kem la 1.0.31 --
        rat cu, de dut khi bon may ao cung goi mot luc. adbutils cache AdbDevice
        nen tu do tro di moi lenh deu hong du may ao van chay binh thuong.

        Chi thu lai voi nhom loi ket noi; loi that su cua lenh van nem ra ngay.
        """
        for attempt in range(retries + 1):
            try:
                return fn(self.device, *a, **kw)
            except Exception as exc:
                msg = str(exc).lower()
                if not any(t in msg for t in self._TRANSIENT) or attempt >= retries:
                    raise
                self._device = None
                time.sleep(1 + attempt * 2)
                self.connect(retries=5, delay=2)

    def restart(self, log=None) -> "Instance":
        """Tat han roi bat lai. Dung khi muon chac may ao o trang thai sach.

        Dung tiep mot may ao dang chay thi mang theo moi thu con sot lai cua
        phien truoc: app dang mo do dang, VPN nua chung, dialog chua tat.
        """
        if self.console.is_running(self.index):
            if log:
                log("may ao dang chay -> tat roi bat lai")
            self.console.quit(self.index)
            self.console.wait_stopped(self.index)
            self._device = None
        return self.start()

    def sh(self, cmd: str, timeout: float = 30.0) -> str:
        """adb shell, tu noi lai neu ket noi rot. Dung cai nay thay cho device.shell()."""
        return self._retry(lambda d: d.shell(cmd, timeout=timeout))

    # ---------- vong doi ----------

    @staticmethod
    def list_adb_devices() -> list[str]:
        """Serial cua moi thiet bi ADB dang thay -- de doi chieu khi doan cong sai."""
        try:
            return [d.serial for d in adbutils.adb.device_list()]
        except Exception:
            return []

    def wait_boot_adb(self, timeout: float = 240.0, poll: float = 2.0) -> None:
        """Doi Android boot xong bang cach hoi THANG cong ADB.

        `LDConsole.wait_boot` di qua `ldconsole adb --command`, va tang passthrough
        do im lang tren mot so ban LDPlayer (nhat la ban tieng Trung): Android da
        san sang tu lau ma lenh van tra ve chuoi rong, nen vong lap poll khong bao
        gio thoat va chi ket thuc bang TimeoutError. Hoi thang cong ADB bo qua
        duoc tang do.
        """
        deadline = time.monotonic() + timeout
        last: Exception | None = None
        while time.monotonic() < deadline:
            try:
                adbutils.adb.connect(self.serial, timeout=5.0)
                dev = adbutils.adb.device(self.serial)
                if dev.shell("getprop sys.boot_completed", timeout=10).strip() == "1":
                    self._device = dev
                    return
            except Exception as exc:  # cong chua mo, adb chua len, device offline...
                last = exc
            time.sleep(poll)
        raise TimeoutError(
            f"{self.serial} khong boot xong trong {timeout}s (loi cuoi: {last}). "
            f"ADB dang thay: {self.list_adb_devices() or 'khong co gi'}"
        )

    def start(self, wait: bool = True, boot_via: str = "adb") -> "Instance":
        """Bat may ao va doi den khi dung duoc.

        boot_via='adb'     -- hoi thang cong ADB (mac dinh, do tin cay cao hon)
        boot_via='console' -- di qua ldconsole, giu lai cho ban nao passthrough on
        """
        self.console.launch(self.index)
        if wait:
            if boot_via == "console":
                self.console.wait_boot(self.index)
                self.connect()
            else:
                self.wait_boot_adb()
        return self

    def stop(self) -> None:
        self._device = None
        self.console.quit(self.index)

    # ---------- thao tac co ban ----------

    def tap(self, x: int, y: int) -> None:
        self._retry(lambda d: d.click(x, y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> None:
        self._retry(lambda d: d.swipe(x1, y1, x2, y2, duration))

    # `adb shell input text` khong nhan space va nuot mot loat ky tu shell.
    # Bang thay the nay port tu InputText() cua AutoLDPlayer.
    _TEXT_ESCAPE = {" ": "%s", **{c: "\\" + c for c in "&<>?:{}[]|;()\\'\""}}

    def scroll(
        self,
        x: int,
        y: int,
        times: int = 1,
        dy: int = 60,
        duration: float = 0.25,
        pause: float = 0.35,
    ) -> None:
        """Cuon tai (x, y) bang `times` cu vuot ngan, moi cu `dy` pixel.

        dy > 0 la ngon tay di XUONG. Tren banh xe chon (picker) thi ngon tay di
        xuong keo danh sach ve phia gia tri truoc do -- nguoc voi truc giac
        "cuon xuong de xem tiep", nen doi dau neu chay ra khong nhu y.

        Vuot nhieu cu ngan chu khong mot cu dai: banh xe co quan tinh, mot cu
        vuot dai bay qua vai chuc nac roi dung o cho khong doan duoc. Cu ngan
        an dut tung nac mot.

        `pause` de banh xe dung han giua hai cu; khong cho thi cu sau noi vao
        da cu truoc thanh mot cu vuot dai.
        """
        for _ in range(times):
            self.swipe(x, y, x, y + dy, duration)
            time.sleep(pause)

    def long_press(self, x: int, y: int, duration: float = 0.8) -> None:
        # swipe tai cho = nhan giu; adb khong co lenh long-press rieng.
        self._retry(lambda d: d.swipe(x, y, x, y, duration))

    def screen_resolution(self) -> tuple[int, int]:
        """Doc do phan giai that tu trong Android (co cache).

        AutoLDPlayer parse `dumpsys display | grep mCurrentDisplayRect` bang
        IndexOf khong kiem tra -1 -> nem exception khi output la.
        `wm size` ngan va on dinh hon nhieu.
        """
        if self._resolution is None:
            out = self.sh("wm size").strip()
            # "Physical size: 540x960" hoac them "Override size: ..."
            line = [l for l in out.splitlines() if "size:" in l][-1]
            w, h = line.split(":")[1].strip().split("x")
            self._resolution = (int(w), int(h))
        return self._resolution

    def tap_percent(self, x_pct: float, y_pct: float) -> None:
        """Bam theo % man hinh (0-100) thay vi pixel.

        Doi resolution thi toa do pixel chet het, con % thi khong.
        """
        w, h = self.screen_resolution()
        self.tap(int(x_pct * w / 100), int(y_pct * h / 100))

    def swipe_percent(
        self, x1: float, y1: float, x2: float, y2: float, duration: float = 0.3
    ) -> None:
        w, h = self.screen_resolution()
        self.swipe(
            int(x1 * w / 100), int(y1 * h / 100),
            int(x2 * w / 100), int(y2 * h / 100),
            duration,
        )

    def text(self, s: str) -> None:
        escaped = "".join(self._TEXT_ESCAPE.get(c, c) for c in s)
        self.sh(f'input text "{escaped}"')

    def key(self, keycode: str | int) -> None:
        self.sh(f"input keyevent {keycode}")

    def back(self) -> None:
        self.key("KEYCODE_BACK")

    def home(self) -> None:
        self.key("KEYCODE_HOME")

    def menu(self) -> None:
        self.key("KEYCODE_APP_SWITCH")

    def airplane_mode(self, on: bool) -> None:
        """Bat/tat che do may bay -- cach nhanh nhat de doi IP khi dung 4G.

        AutoLDPlayer.PlanModeOff() bi loi copy-paste: no set airplane_mode_on 1
        y het PlanModeOn, tuc la khong bao gio tat duoc.
        """
        self.sh(f"settings put global airplane_mode_on {1 if on else 0}")
        self.sh(
            f"am broadcast -a android.intent.action.AIRPLANE_MODE --ez state {str(on).lower()}"
        )

    def start_app(self, package: str) -> None:
        self.console.run_app(self.index, package)

    def stop_app(self, package: str) -> None:
        self.console.kill_app(self.index, package)

    # ---------- app qua ADB (khong di qua ldconsole) ----------

    def list_packages(self, third_party: bool = True) -> list[str]:
        """Package dang cai. third_party=True bo qua app he thong cho de nhin."""
        out = self.sh(f"pm list packages{' -3' if third_party else ''}")
        return sorted(
            line.split(":", 1)[1].strip()
            for line in out.splitlines()
            if line.startswith("package:")
        )

    def find_package(self, keyword: str) -> list[str]:
        """Tim package theo tu khoa, vd find_package('vpn')."""
        k = keyword.lower()
        return [p for p in self.list_packages(third_party=False) if k in p.lower()]

    def start_app_adb(self, package: str) -> None:
        """Mo app qua ADB thay vi `ldconsole runapp`.

        Dung khi tang passthrough cua ldconsole khong dang tin -- xem
        wait_boot_adb(). `monkey` tu tim LAUNCHER activity nen khoi phai
        biet ten activity.
        """
        out = self.sh(
            f"monkey -p {package} -c android.intent.category.LAUNCHER 1"
        )
        # monkey tra ve exit code 0 ca khi that bai -> phai doc stdout.
        if "No activities found" in out or "Error" in out or "Exception" in out:
            raise RuntimeError(f"Khong mo duoc {package}:\n{out.strip()}")

    def stop_app_adb(self, package: str) -> None:
        self.sh(f"am force-stop {package}")

    def clear_app(self, package: str) -> None:
        """Xoa sach du lieu + cache cua app, dua no ve nhu vua cai.

        Xoa ca dang nhap. Tren farm nhan ban day la thu can lam voi app choi
        game -- moi clone phai la mot phien rieng, khong thi ca 4 may cung mot
        tai khoan. Nhung TUYET DOI khong goi voi app VPN: mat luon dang nhap
        ExpressVPN va consent VPN da cap, phai lam tay lai tung may.

        pm clear tu force-stop app truoc nen khong can tat rieng.
        """
        out = self.sh(f"pm clear {package}", timeout=60)
        if "success" not in out.lower():
            raise RuntimeError(f"pm clear {package} that bai: {out.strip()!r}")

    def is_app_running(self, package: str) -> bool:
        return bool(self.sh(f"pidof {package}").strip())

    def current_app(self) -> str | None:
        """Package dang o foreground, None neu khong doc duoc.

        Khong nem exception: format dumpsys doi theo phien ban Android, va viec
        khong doc duoc app dang chay khong dang lam hong ca script.
        """
        for cmd, marker in (
            ("dumpsys activity activities", "mResumedActivity"),
            ("dumpsys window", "mCurrentFocus"),
        ):
            try:
                for line in self.sh(cmd).splitlines():
                    if marker not in line:
                        continue
                    for tok in line.split():
                        if "/" in tok:
                            return tok.split("/", 1)[0].lstrip("{")
            except Exception:
                continue
        return None

    # ---------- doc cay giao dien (uiautomator) ----------

    def dump_ui(self) -> str:
        """XML cay giao dien dang hien.

        On dinh hon nhan dien anh: khong phu thuoc resolution, khong can chup
        lai anh mau moi khi doi Spec. Doi lai thi cham hon (~1s/lan) va mot so
        app ve bang canvas/game engine se khong lo ra node nao -- Roblox la
        vi du, nen phan trong game van phai dung tap_image.
        """
        # uiautomator tu choi dump khi man hinh chua "idle" -- app dang chay
        # animation (nut Connect cua VPN la vi du) se truot lien may lan.
        # Thu lai vai lan re hon la de goi ham nem ra ngoai.
        last = ""
        for _ in range(4):
            last = self.sh("uiautomator dump /sdcard/ui.xml", timeout=30)
            if "ERROR" not in last.upper() and "could not" not in last.lower():
                return self.sh("cat /sdcard/ui.xml", timeout=30)
            time.sleep(2)
        raise RuntimeError(f"uiautomator dump that bai sau 4 lan: {last.strip()}")

    @staticmethod
    def _node_center(bounds: str) -> tuple[int, int]:
        """'[12,34][56,78]' -> (34, 56)"""
        nums = [int(n) for n in re.findall(r"-?\d+", bounds)]
        x1, y1, x2, y2 = nums[:4]
        return (x1 + x2) // 2, (y1 + y2) // 2

    def ui_nodes(self) -> list[dict]:
        """Moi node co bounds, kem text/desc/id/class de doi chieu."""
        try:
            root = ET.fromstring(self.dump_ui())
        except ET.ParseError as exc:
            raise RuntimeError(f"XML uiautomator hong: {exc}") from exc
        nodes = []
        for n in root.iter("node"):
            b = n.get("bounds")
            if not b:
                continue
            nodes.append({
                "text": n.get("text", ""),
                "desc": n.get("content-desc", ""),
                "id": n.get("resource-id", ""),
                "class": n.get("class", ""),
                "clickable": n.get("clickable") == "true",
                "bounds": b,
                "center": self._node_center(b),
            })
        return nodes

    def find_node(
        self,
        text: str | None = None,
        desc: str | None = None,
        res_id: str | None = None,
        clickable: bool | None = None,
        exact: bool = False,
        nodes: list[dict] | None = None,
    ) -> dict | None:
        """Tim node dau tien khop. So khong phan biet hoa thuong, mac dinh khop mot phan."""
        def hit(have: str, want: str) -> bool:
            return have == want if exact else want.lower() in have.lower()

        for n in nodes if nodes is not None else self.ui_nodes():
            if text is not None and not hit(n["text"], text):
                continue
            if desc is not None and not hit(n["desc"], desc):
                continue
            if res_id is not None and not hit(n["id"], res_id):
                continue
            if clickable is not None and n["clickable"] != clickable:
                continue
            return n
        return None

    def wait_node(self, timeout: float = 30.0, poll: float = 1.5, **kw) -> dict:
        deadline = time.monotonic() + timeout
        last: Exception | None = None
        while time.monotonic() < deadline:
            try:
                n = self.find_node(**kw)
                if n:
                    return n
            except RuntimeError as exc:  # dump loi luc man hinh dang chuyen canh
                last = exc
            time.sleep(poll)
        raise TimeoutError(f"Khong thay node {kw} sau {timeout}s (loi cuoi: {last})")

    def tap_node(self, timeout: float | None = None, **kw) -> bool:
        """timeout=None -> thu mot lan, False neu khong thay. Co timeout -> doi, nem neu het gio."""
        n = self.wait_node(timeout=timeout, **kw) if timeout else self.find_node(**kw)
        if n is None:
            return False
        self.tap(*n["center"])
        return True

    # ---------- VPN ----------

    def vpn_connected(self) -> bool:
        """Co interface tun khong -- moc that su, khong tin chu tren man hinh.

        App bao 'Connected' ma khong co tun0 nghia la duong ham chua dung duoc.
        """
        out = self.sh("ip addr", timeout=15)
        # Doi hoi interface tun CO DIA CHI IP, khong chi ton tai: tun0 co the
        # nam do o trang thai DOWN tu phien truoc ma khong dan di dau ca.
        for block in re.split(r"\n(?=\s*\d+:)", out):
            if re.match(r"\s*\d+:\s*tun\d", block) and "inet " in block:
                return True
        return False

    def wait_vpn(self, timeout: float = 90.0, poll: float = 3.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.vpn_connected():
                return
            time.sleep(poll)
        raise TimeoutError(f"VPN khong len sau {timeout}s (khong thay interface tun)")

    def grant_vpn(self, package: str) -> bool:
        """Cho phep app tu dung VPN, bo qua hop thoai xac nhan cua he thong.

        CAN ROOT. LDPlayer bat root duoc bang console.modify(idx, root=True)
        roi khoi dong lai may ao. Tra ve False neu khong an -- luc do phai bam
        tay vao nut OK trong hop thoai "Connection request".
        """
        out = self.sh(f"appops set {package} ACTIVATE_VPN allow")
        return not out.strip()

    def set_proxy(self, ip: str, port: int) -> None:
        """Moi may ao mot IP rieng -- can thiet khi chay farm nhieu tai khoan."""
        self.sh(f"settings put global http_proxy {ip}:{port}")

    def clear_proxy(self) -> None:
        self.sh("settings put global http_proxy :0")

    # ---------- nhin ----------

    def screenshot(self) -> np.ndarray:
        """Tra ve anh BGR cho OpenCV."""
        pil = self._retry(lambda d: d.screenshot())
        return cv2.cvtColor(np.array(pil.convert("RGB")), cv2.COLOR_RGB2BGR)

    def find(
        self,
        template: str | Path | np.ndarray,
        threshold: float = 0.85,
        screen: np.ndarray | None = None,
    ) -> tuple[int, int] | None:
        """Tim anh mau tren man hinh, tra ve tam cua vung khop hoac None."""
        tpl = cv2.imread(str(template)) if not isinstance(template, np.ndarray) else template
        if tpl is None:
            raise FileNotFoundError(f"Khong doc duoc anh mau: {template}")
        img = self.screenshot() if screen is None else screen
        res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
        _, score, _, loc = cv2.minMaxLoc(res)
        if score < threshold:
            return None
        h, w = tpl.shape[:2]
        return loc[0] + w // 2, loc[1] + h // 2

    def wait_for(
        self,
        template: str | Path,
        timeout: float = 30.0,
        threshold: float = 0.85,
        poll: float = 1.0,
    ) -> tuple[int, int]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pos = self.find(template, threshold)
            if pos:
                return pos
            time.sleep(poll)
        raise TimeoutError(f"Khong thay {template} sau {timeout}s")

    def tap_image(
        self,
        template: str | Path,
        threshold: float = 0.85,
        timeout: float | None = None,
    ) -> bool:
        """Tim anh roi bam vao giua no.

        timeout=None -> thu mot lan, tra ve False neu khong thay.
        timeout=<so> -> cho toi khi thay, nem TimeoutError neu het gio.
        """
        if timeout is None:
            pos = self.find(template, threshold)
            if pos is None:
                return False
        else:
            pos = self.wait_for(template, timeout, threshold)
        self.tap(*pos)
        return True

    def find_any(
        self,
        templates: "list[str | Path] | str | Path",
        threshold: float = 0.85,
    ) -> tuple[str, tuple[int, int]] | None:
        """Quet nhieu anh mau tren CUNG mot frame.

        AutoLDPlayer.FindImage() chup lai man hinh cho tung anh mau -- rat cham.
        Chup mot lan roi so tat ca nhanh hon nhieu, va tranh truong hop
        man hinh doi giua cac lan so.

        Tra ve (ten anh khop, toa do tam) hoac None.
        """
        if isinstance(templates, (str, Path)):
            d = Path(templates)
            paths = sorted(d.iterdir()) if d.is_dir() else [d]
        else:
            paths = [Path(t) for t in templates]

        screen = self.screenshot()
        for tpl in paths:
            pos = self.find(tpl, threshold, screen=screen)
            if pos:
                return tpl.name, pos
        return None
