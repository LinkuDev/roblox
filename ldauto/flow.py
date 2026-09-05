"""Chay cung mot kich ban tren nhieu may ao song song.

Moi may ao mot thread. Cong viec o day gan nhu toan bo la doi I/O (adb, boot,
mang) chu khong phai tinh toan, nen GIL khong phai van de -- khoi can process.
"""

from __future__ import annotations

import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from .instance import Instance

_print_lock = threading.Lock()


class Log:
    """In co tien to [index], khoa lai de dong cua cac thread khong dan vao nhau."""

    def __init__(self, tag: str):
        self.tag = tag

    def __call__(self, msg: str) -> None:
        with _print_lock:
            print(f"[{self.tag}] {msg}", flush=True)


@dataclass
class FlowResult:
    index: int
    ok: bool
    error: str | None = None
    elapsed: float = 0.0


def run_parallel(
    instances: list[Instance],
    fn: Callable[[Instance, Log], None],
    stagger: float = 20.0,
    max_workers: int | None = None,
) -> list[FlowResult]:
    """Chay fn(inst, log) tren tung may ao, song song.

    stagger: giay giua moi lan khoi dong. Bat 4 may ao cung mot luc lam nghen
    CPU va dia, may ao boot cham hon han hoac treo han. Le nhau ra thi tong
    thoi gian gan nhu khong doi ma on dinh hon nhieu.

    Mot may ao hong khong keo do cac may con lai -- loi duoc bat va tra ve
    trong FlowResult de xem lai o cuoi.
    """

    def worker(n: int, inst: Instance) -> FlowResult:
        log = Log(str(inst.index))
        t0 = time.monotonic()
        if n and stagger:
            time.sleep(stagger * n)
        try:
            fn(inst, log)
            dt = time.monotonic() - t0
            log(f"xong sau {dt:.0f}s")
            return FlowResult(inst.index, True, elapsed=dt)
        except Exception as exc:
            dt = time.monotonic() - t0
            log(f"HONG: {type(exc).__name__}: {exc}")
            with _print_lock:
                traceback.print_exc()
            return FlowResult(inst.index, False, f"{type(exc).__name__}: {exc}", dt)

    with ThreadPoolExecutor(max_workers=max_workers or len(instances)) as pool:
        futures = [pool.submit(worker, n, inst) for n, inst in enumerate(instances)]
        return [f.result() for f in futures]


def report(results: list[FlowResult]) -> int:
    """In tong ket, tra ve so may ao hong (dung lam exit code)."""
    ok = [r for r in results if r.ok]
    bad = [r for r in results if not r.ok]
    print("\n" + "=" * 56)
    print(f"KET QUA: {len(ok)}/{len(results)} may ao xong")
    for r in bad:
        print(f"  [FAIL] index={r.index}: {r.error}")
    print("=" * 56)
    return len(bad)
