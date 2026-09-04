"""Dieu khien ben trong mot may ao: tap, swipe, chup man hinh, tim anh."""

from __future__ import annotations

import time
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

    # ---------- vong doi ----------

    def start(self, wait: bool = True) -> "Instance":
        self.console.launch(self.index)
        if wait:
            self.console.wait_boot(self.index)
            self.connect()
        return self

    def stop(self) -> None:
        self._device = None
        self.console.quit(self.index)

    # ---------- thao tac co ban ----------

    def tap(self, x: int, y: int) -> None:
        self.device.click(x, y)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> None:
        self.device.swipe(x1, y1, x2, y2, duration)

    # `adb shell input text` khong nhan space va nuot mot loat ky tu shell.
    # Bang thay the nay port tu InputText() cua AutoLDPlayer.
    _TEXT_ESCAPE = {" ": "%s", **{c: "\\" + c for c in "&<>?:{}[]|;()\\'\""}}

    def long_press(self, x: int, y: int, duration: float = 0.8) -> None:
        # swipe tai cho = nhan giu; adb khong co lenh long-press rieng.
        self.device.swipe(x, y, x, y, duration)

    def screen_resolution(self) -> tuple[int, int]:
        """Doc do phan giai that tu trong Android (co cache).

        AutoLDPlayer parse `dumpsys display | grep mCurrentDisplayRect` bang
        IndexOf khong kiem tra -1 -> nem exception khi output la.
        `wm size` ngan va on dinh hon nhieu.
        """
        if self._resolution is None:
            out = self.device.shell("wm size").strip()
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
        self.device.shell(f'input text "{escaped}"')

    def key(self, keycode: str | int) -> None:
        self.device.shell(f"input keyevent {keycode}")

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
        self.device.shell(f"settings put global airplane_mode_on {1 if on else 0}")
        self.device.shell(
            f"am broadcast -a android.intent.action.AIRPLANE_MODE --ez state {str(on).lower()}"
        )

    def start_app(self, package: str) -> None:
        self.console.run_app(self.index, package)

    def stop_app(self, package: str) -> None:
        self.console.kill_app(self.index, package)

    def set_proxy(self, ip: str, port: int) -> None:
        """Moi may ao mot IP rieng -- can thiet khi chay farm nhieu tai khoan."""
        self.device.shell(f"settings put global http_proxy {ip}:{port}")

    def clear_proxy(self) -> None:
        self.device.shell("settings put global http_proxy :0")

    # ---------- nhin ----------

    def screenshot(self) -> np.ndarray:
        """Tra ve anh BGR cho OpenCV."""
        pil = self.device.screenshot()
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
