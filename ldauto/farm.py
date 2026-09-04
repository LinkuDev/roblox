"""Tao hang loat may ao voi cau hinh dong nhat."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .console import LDConsole
from .instance import Instance


@dataclass
class Spec:
    """Cau hinh mong muon cho mot may ao."""

    width: int = 540
    height: int = 960
    dpi: int = 240
    cpu: int = 2
    memory: int = 2048
    # Moi may ao mot bo dinh danh rieng, tranh bi coi la cung mot thiet bi.
    randomize_ids: bool = True
    extra: dict = field(default_factory=dict)


class Farm:
    def __init__(self, console: LDConsole):
        self.console = console

    def ensure(self, name: str, spec: Spec, source: int | str | None = None) -> Instance:
        """Tao may ao neu chua co, ap cau hinh, tra ve handle.

        source != None -> nhan ban tu may ao do (nhanh hon, giu nguyen app da cai).
        """
        info = self.console.find(name)
        if info is None:
            if source is None:
                self.console.create(name)
            else:
                # Nhan ban may ao DANG CHAY = copy o dia dang bi ghi -> anh hong.
                # Phai tat nguon truoc, khong co cach nao khac.
                if self.console.is_running(source):
                    self.console.quit(source)
                    self._wait_stopped(source)
                self.console.copy_from(name, source)
            info = self.console.find(name)
            if info is None:
                raise RuntimeError(f"Tao may ao {name!r} that bai")

        # resolution chi an khi may ao dang tat -> tat truoc neu can.
        if self.console.is_running(name):
            self.console.quit(name)

        ids = {}
        if spec.randomize_ids:
            ids = {"imei": "auto", "mac": "auto", "android_id": "auto"}

        self.console.modify(
            name,
            width=spec.width,
            height=spec.height,
            dpi=spec.dpi,
            cpu=spec.cpu,
            memory=spec.memory,
            **ids,
            **spec.extra,
        )
        return Instance(self.console, info.index)

    def _wait_stopped(self, instance: int | str, timeout: float = 60.0, poll: float = 1.0) -> None:
        """`quit` tra ve ngay lap tuc, nhung tien trinh VBox con song them vai giay.

        Copy trong khoang do van dinh o dia dang mo -> phai doi that su tat.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            info = self.console.find(instance)
            if info is None or not info.running:
                return
            time.sleep(poll)
        raise TimeoutError(f"{instance} khong tat trong {timeout}s, khong dam bao copy an toan")

    def ensure_many(
        self,
        prefix: str,
        count: int,
        spec: Spec,
        source: int | str | None = None,
    ) -> list[Instance]:
        return [self.ensure(f"{prefix}{i}", spec, source) for i in range(count)]
