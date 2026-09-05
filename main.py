"""GUI dieu khien farm Roblox -- cho stakeholder bam nut, khong dung terminal.

    python main.py

Nut: Bat dau / Tam dung / Dung / Xuat TXT. Log hien truc tiep, trang thai
dem so acc theo tung status. Dung tkinter (co san trong Python, khong cai them).
"""

from __future__ import annotations

import os
import queue
import sqlite3
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

import roblox_flow as rf  # noqa: E402
from ldauto import AccountStore, ensure_warning_prefix  # noqa: E402


class _QueueWriter:
    """File-like: gom stdout/stderr thanh tung dong roi day vao queue.

    Bat ca print() thuong (vd build_instances) lan traceback, khong chi Log.
    An toan nhieu thread: moi thread trong run_parallel deu ghi vao day.
    """

    def __init__(self, q: "queue.Queue[str]"):
        self.q = q
        self.buf = ""
        self.lock = threading.Lock()

    def write(self, text: str):
        with self.lock:
            self.buf += text
            while "\n" in self.buf:
                line, self.buf = self.buf.split("\n", 1)
                self.q.put(line)

    def flush(self):
        pass


# ---------------------------------------------------------------------------
# Xuat file txt (dung chung logic voi xuat_txt.py)
# ---------------------------------------------------------------------------
def export_txt(db: str, out: str, only_cookie: bool = True) -> int:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT username, password, cookie FROM accounts ORDER BY id").fetchall()
    con.close()
    lines = []
    for r in rows:
        ck = r["cookie"] or ""
        if not ck and only_cookie:
            continue
        if ck:
            ck = ensure_warning_prefix(ck)
        lines.append(f"{r['username']}:{r['password']}:{ck}")
    Path(out).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


def db_stats(db: str) -> dict[str, int]:
    """Dem acc theo status + so co cookie. Doc-only, khong khoa DB dang ghi."""
    if not os.path.exists(db):
        return {}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute("SELECT status, cookie FROM accounts").fetchall()
        con.close()
    except sqlite3.Error:
        return {}
    out = {"tong": len(rows), "cookie": sum(1 for _, c in rows if c)}
    for st, _ in rows:
        out[st] = out.get(st, 0) + 1
    return out


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Roblox Farm - LDPlayer")
        root.geometry("760x560")

        self.log_q: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.restart_pending = False   # dat khi bam Chay lai luc dang chay

        self._build_config()
        self._build_controls()
        self._build_status()
        self._build_log()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(150, self._pump)      # bom log + trang thai vao UI

    # ----- dung UI -----
    def _build_config(self):
        f = ttk.LabelFrame(self.root, text="Cau hinh")
        f.pack(fill="x", padx=8, pady=6)

        self.var_ld = tk.StringVar(value=rf.LDCONSOLE)
        self.var_db = tk.StringVar(value="accounts.db")
        self.var_rounds = tk.IntVar(value=0)
        self.var_clones = tk.IntVar(value=rf.CLONES)
        self.var_slow = tk.DoubleVar(value=1.0)

        row = ttk.Frame(f); row.pack(fill="x", padx=6, pady=3)
        ttk.Label(row, text="ldconsole:", width=10).pack(side="left")
        ttk.Entry(row, textvariable=self.var_ld).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="...", width=3, command=self._pick_ld).pack(side="left", padx=3)

        row = ttk.Frame(f); row.pack(fill="x", padx=6, pady=3)
        ttk.Label(row, text="DB:", width=10).pack(side="left")
        ttk.Entry(row, textvariable=self.var_db).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="...", width=3, command=self._pick_db).pack(side="left", padx=3)

        row = ttk.Frame(f); row.pack(fill="x", padx=6, pady=3)
        ttk.Label(row, text="So vong (0=vo han):").pack(side="left")
        ttk.Spinbox(row, from_=0, to=9999, width=6, textvariable=self.var_rounds).pack(side="left", padx=4)
        ttk.Label(row, text="So clone:").pack(side="left", padx=(12, 0))
        ttk.Spinbox(row, from_=0, to=64, width=5, textvariable=self.var_clones).pack(side="left", padx=4)
        ttk.Label(row, text="He so cho:").pack(side="left", padx=(12, 0))
        ttk.Spinbox(row, from_=0.5, to=5, increment=0.5, width=5,
                    textvariable=self.var_slow).pack(side="left", padx=4)
        self.config_widgets = f

    def _build_controls(self):
        f = ttk.Frame(self.root); f.pack(fill="x", padx=8, pady=4)
        self.btn_start = ttk.Button(f, text="▶ Bat dau", command=self._start)
        self.btn_restart = ttk.Button(f, text="\U0001f504 Chay lai", command=self._restart)
        self.btn_export = ttk.Button(f, text="\U0001f4be Xuat TXT", command=self._export)
        for b in (self.btn_start, self.btn_restart, self.btn_export):
            b.pack(side="left", padx=4)

    def _build_status(self):
        f = ttk.LabelFrame(self.root, text="Trang thai")
        f.pack(fill="x", padx=8, pady=4)
        self.var_status = tk.StringVar(value="chua chay")
        ttk.Label(f, textvariable=self.var_status, font=("TkDefaultFont", 10)).pack(
            anchor="w", padx=8, pady=4)

    def _build_log(self):
        f = ttk.LabelFrame(self.root, text="Nhat ky")
        f.pack(fill="both", expand=True, padx=8, pady=6)
        self.txt = tk.Text(f, wrap="none", height=14, state="disabled",
                           bg="#111", fg="#ddd", font=("Consolas", 9))
        sb = ttk.Scrollbar(f, command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.txt.pack(side="left", fill="both", expand=True)

    # ----- chon file -----
    def _pick_ld(self):
        p = filedialog.askopenfilename(title="Chon ldconsole.exe / dnconsole.exe",
                                       filetypes=[("exe", "*.exe"), ("all", "*.*")])
        if p:
            self.var_ld.set(p)

    def _pick_db(self):
        p = filedialog.askopenfilename(title="Chon accounts.db",
                                       filetypes=[("db", "*.db"), ("all", "*.*")])
        if p:
            self.var_db.set(p)

    # ----- dieu khien -----
    def _running(self) -> bool:
        return self.worker is not None and self.worker.is_alive()

    def _start(self):
        if self._running():
            return
        rf.STOP.clear()
        rf.RESUME.set()
        # nap cau hinh tu form vao module flow
        rf.LDCONSOLE = self.var_ld.get()
        rf.CLONES = self.var_clones.get()
        rf.ROUNDS = self.var_rounds.get()
        rf.SLOW = self.var_slow.get()

        self._set_config_state("disabled")
        self.btn_start.config(state="disabled")

        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def _restart(self):
        """Chay lai tu dau -- giong chay lai `python examples/roblox_flow.py`.

        Dang chay: bao cac luong dung (xong vong hien tai) roi tu khoi dong lai
        khi chung thoat -- viec khoi dong lai do _pump lo, khong chan GUI.
        Dang ranh: chay ngay nhu Start.
        """
        if self._running():
            self.restart_pending = True
            rf.STOP.set()
            rf.RESUME.set()   # go pause de luong thoat duoc o gate
            rf.Log("main")("Chay lai: cho cac luong xong vong hien tai roi bat lai...")
        else:
            self._start()

    def _run(self):
        """Chay trong thread nen -- KHONG dung tkinter o day."""
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = _QueueWriter(self.log_q)  # bat moi print + log
        log = rf.Log("main")
        try:
            console = rf.LDConsole(self.var_ld.get())
            rf.STORE = AccountStore(self.var_db.get())
            log(f"DB: {os.path.abspath(self.var_db.get())} "
                f"({rf.STORE.count()} ban ghi)")
            console.global_setting(fps=30, audio=False, fast_play=True)

            # Goi dung ham ma script dung -> Start chay Y HET python roblox_flow.py
            # (mac dinh: xoa Roblox moi vong, xep cua so, tat may dang chay truoc).
            results = rf.run_farm(console)
            rf.report(results)
            log("=== da dung tat ca luong ===")
        except Exception as exc:
            log(f"LOI: {type(exc).__name__}: {exc}")
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    def _export(self):
        db = self.var_db.get()
        if not os.path.exists(db):
            messagebox.showerror("Loi", f"Khong thay DB:\n{os.path.abspath(db)}")
            return
        out = filedialog.asksaveasfilename(
            title="Luu file txt", defaultextension=".txt",
            initialfile="acc.txt", filetypes=[("Text", "*.txt")])
        if not out:
            return
        try:
            n = export_txt(db, out, only_cookie=True)
        except Exception as exc:
            messagebox.showerror("Loi", str(exc))
            return
        messagebox.showinfo(
            "Xong", f"Da xuat {n} acc (co cookie) ->\n{out}\n\n"
            "File chua cookie = credential song, giu can than.")

    # ----- bom UI dinh ky -----
    def _pump(self):
        # log
        drained = 0
        while drained < 200:
            try:
                line = self.log_q.get_nowait()
            except queue.Empty:
                break
            self._append(line)
            drained += 1

        # trang thai
        st = db_stats(self.var_db.get())
        if st:
            done = st.get("done", 0)
            failed = sum(v for k, v in st.items() if k.startswith("failed"))
            parts = [f"tong {st['tong']}", f"xong {done}",
                     f"co cookie {st['cookie']}", f"loi {failed}"]
            run = "DANG CHAY" if self._running() else "dung"
            self.var_status.set(f"[{run}]  " + " | ".join(parts))

        # worker vua ket thuc
        if not self._running() and self.btn_start["state"] == "disabled":
            self.btn_start.config(state="normal")
            self._set_config_state("normal")
            if self.restart_pending:
                self.restart_pending = False
                self._start()   # khoi dong lai vong moi

        self.root.after(200, self._pump)

    def _append(self, line: str):
        self.txt.config(state="normal")
        self.txt.insert("end", line + "\n")
        self.txt.see("end")
        # gioi han ~1000 dong cho khoi phinh bo nho
        if int(self.txt.index("end-1c").split(".")[0]) > 1000:
            self.txt.delete("1.0", "200.0")
        self.txt.config(state="disabled")

    def _set_config_state(self, state: str):
        for child in self.config_widgets.winfo_children():
            for w in child.winfo_children():
                try:
                    w.config(state=state)
                except tk.TclError:
                    pass

    def _on_close(self):
        if self._running():
            if not messagebox.askyesno("Thoat", "Cac luong dang chay. Van thoat?"):
                return
            rf.STOP.set()
            rf.RESUME.set()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
