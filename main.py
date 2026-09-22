"""GUI dieu khien farm Roblox -- cho stakeholder bam nut, khong dung terminal.

    python main.py

Nut: Bat dau / Tam dung / Dung / Xuat TXT. Log hien truc tiep, trang thai
dem so acc theo tung status. Dung tkinter (co san trong Python, khong cai them).
"""

from __future__ import annotations

import json
import os
import queue
import sqlite3
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))


def app_dir() -> Path:
    """Thu muc de dat file du lieu (accounts.db, file xuat...).

    Khi dong goi thanh .exe (PyInstaller): thu muc CHUA exe -- nen DB nam ngang
    hang voi exe, khong phai thu muc tam _MEIPASS. Khi chay python: canh main.py.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return ROOT


def _config_path() -> Path:
    return app_dir() / "config.json"


def load_config() -> dict:
    """Doc config.json canh exe. Rong/loi -> {} (dung mac dinh)."""
    try:
        return json.loads(_config_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict) -> None:
    try:
        _config_path().write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


import roblox_flow as rf  # noqa: E402
from ldauto import AccountStore, ensure_warning_prefix  # noqa: E402
from ldauto import telemetry  # noqa: E402


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
        # Redirect ngay: che do --windowed cua PyInstaller co sys.stdout = None,
        # moi print()/Log se loi neu khong huong ve queue. Giu suot doi app.
        sys.stdout = sys.stderr = _QueueWriter(self.log_q)
        self.worker: threading.Thread | None = None
        self.restart_pending = False   # dat khi bam Chay lai luc dang chay
        self._ready = False            # chan _save_config chay khi dang dung UI
        self._cfg = load_config()      # nap cau hinh da luu (nguon, duong dan...)

        # Notebook 2 tab: "Tao acc" (luong cu) va "Login lay cookie" (luong moi).
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="x", padx=4, pady=4)
        self.tab_farm = ttk.Frame(self.nb)
        self.tab_login = ttk.Frame(self.nb)
        self.nb.add(self.tab_farm, text="Tao acc")
        self.nb.add(self.tab_login, text="Login lay cookie")

        self._build_config()      # -> tab_farm
        self._build_sources()     # -> tab_farm
        self._build_controls()    # -> tab_farm
        self._build_login()       # -> tab_login
        self._build_status()      # -> root (chung, duoi notebook)
        self._build_log()         # -> root (chung)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._ready = True

        # Ghi nhan mo app + moc so acc luc mo, de tinh "lam duoc bao nhieu acc"
        # khi dong app.
        self._t_start = time.time()
        self._t_baseline = db_stats(self.var_db.get()).get("tong", 0)
        telemetry.log("app_open", accounts_total=self._t_baseline)

        self.root.after(150, self._pump)      # bom log + trang thai vao UI

    # ----- dung UI -----
    def _build_config(self):
        f = ttk.LabelFrame(self.tab_farm, text="Cau hinh")
        f.pack(fill="x", padx=8, pady=6)

        c = self._cfg
        self.var_ld = tk.StringVar(value=c.get("ldconsole", rf.LDCONSOLE))
        self.var_db = tk.StringVar(value=c.get("db", str(app_dir() / "accounts.db")))
        self.var_rounds = tk.IntVar(value=c.get("rounds", 0))
        self.var_clones = tk.IntVar(value=c.get("clones", rf.CLONES))
        self.var_slow = tk.DoubleVar(value=c.get("slow", 1.0))
        for v in (self.var_ld, self.var_db, self.var_rounds, self.var_clones, self.var_slow):
            v.trace_add("write", lambda *a: self._save_config())

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

    def _build_sources(self):
        """Danh sach may nguon de clone. Moi nguon clone theo 'So clone'.

        Bat dau 1 dong 'roblox'. Nut + them dong, mac dinh tang dan:
        roblox2, roblox3... -- van sua tay duoc. Ten do dung de search + clone.
        """
        f = ttk.LabelFrame(self.tab_farm,
                           text="Nguon (may goc de clone) - moi nguon clone theo So clone")
        f.pack(fill="x", padx=8, pady=4)
        self.sources_container = ttk.Frame(f)
        self.sources_container.pack(fill="x", padx=6, pady=3)
        self.source_rows: list[tuple] = []
        for name in (self._cfg.get("sources") or ["roblox"]):
            self._add_source_row(name)
        ttk.Button(f, text="+ Them nguon",
                   command=lambda: self._add_source_row()).pack(anchor="w", padx=6, pady=(0, 5))
        self.sources_widget = f

    def _add_source_row(self, default: str | None = None):
        n = len(self.source_rows)
        if default is None:
            default = "roblox" if n == 0 else f"roblox{n + 1}"
        var = tk.StringVar(value=default)
        var.trace_add("write", lambda *a: self._save_config())
        row = ttk.Frame(self.sources_container)
        row.pack(fill="x", pady=1)
        ttk.Label(row, text=f"#{n + 1}", width=4).pack(side="left")
        ttk.Entry(row, textvariable=var, width=28).pack(side="left")
        ttk.Button(row, text="\u2013", width=3,
                   command=lambda: self._remove_source_row(row, var)).pack(side="left", padx=3)
        self.source_rows.append((row, var))
        self._save_config()

    def _remove_source_row(self, row, var):
        if len(self.source_rows) <= 1:      # giu it nhat 1 nguon
            return
        row.destroy()
        self.source_rows = [(r, v) for (r, v) in self.source_rows if v is not var]
        self._save_config()

    def _source_names(self, dedup: bool = False) -> list[str]:
        names, seen = [], set()
        for _, v in self.source_rows:
            n = v.get().strip()
            if not n or (dedup and n in seen):
                continue
            seen.add(n)
            names.append(n)
        return names

    def _save_config(self) -> None:
        if not self._ready:
            return
        try:
            save_config({
                "ldconsole": self.var_ld.get(),
                "db": self.var_db.get(),
                "rounds": self.var_rounds.get(),
                "clones": self.var_clones.get(),
                "slow": self.var_slow.get(),
                "sources": self._source_names(),
            })
        except Exception:
            pass

    def _build_controls(self):
        f = ttk.Frame(self.tab_farm); f.pack(fill="x", padx=8, pady=4)
        self.btn_start = ttk.Button(f, text="▶ Bat dau", command=self._start)
        self.btn_restart = ttk.Button(f, text="\U0001f504 Chay lai", command=self._restart)
        self.btn_stopld = ttk.Button(f, text="\u23f9 Tat LD", command=self._stop_all_ld)
        self.btn_export = ttk.Button(f, text="\U0001f4be Xuat TXT", command=self._export)
        for b in (self.btn_start, self.btn_restart, self.btn_stopld, self.btn_export):
            b.pack(side="left", padx=4)
        # Dat tach han sang phai: bam nham nut nay la mat sach kho tai khoan.
        self.btn_clear = ttk.Button(f, text="\U0001f5d1 Xoa DB", command=self._clear_db)
        self.btn_clear.pack(side="right", padx=4)

    def _build_login(self):
        """Tab LOGIN: dan danh sach user:pass, dang nhap tung acc lay cookie.

        Dung chung cau hinh ldconsole/DB/nguon/so clone o tab 'Tao acc'.
        """
        f = self.tab_login
        lf = ttk.LabelFrame(f, text="Danh sach user:pass (moi dong mot tai khoan)")
        lf.pack(fill="both", expand=True, padx=8, pady=6)
        self.login_text = tk.Text(lf, height=8, font=("Consolas", 9))
        self.login_text.pack(fill="both", expand=True, padx=6, pady=4)

        row = ttk.Frame(f); row.pack(fill="x", padx=8, pady=4)
        ttk.Button(row, text="\U0001f4c2 Mo file...",
                   command=self._load_login_file).pack(side="left", padx=4)
        self.btn_login_start = ttk.Button(row, text="▶ Bat dau login",
                                          command=self._start_login)
        self.btn_login_start.pack(side="left", padx=4)
        ttk.Button(row, text="⏹ Tat LD",
                   command=self._stop_all_ld).pack(side="left", padx=4)
        ttk.Button(row, text="\U0001f4be Xuat TXT",
                   command=self._export).pack(side="left", padx=4)
        ttk.Label(f, foreground="#888",
                  text="Dung chung ldconsole / DB / Nguon / So clone o tab 'Tao acc'. "
                       "So clone = 0 -> chi dung may nguon.").pack(anchor="w", padx=10,
                                                                   pady=(0, 4))

    def _load_login_file(self):
        p = filedialog.askopenfilename(
            title="Chon file user:pass", filetypes=[("Text", "*.txt"), ("all", "*.*")])
        if not p:
            return
        try:
            data = Path(p).read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            messagebox.showerror("Loi", str(exc))
            return
        self.login_text.delete("1.0", "end")
        self.login_text.insert("1.0", data)

    def _start_login(self):
        if self._running():
            return
        accounts = []
        for line in self.login_text.get("1.0", "end").splitlines():
            line = line.strip()
            if line and ":" in line:
                u, p = line.split(":", 1)
                if u.strip():
                    accounts.append((u.strip(), p.strip()))
        if not accounts:
            messagebox.showerror("Loi", "Chua co user:pass nao (moi dong: user:pass)")
            return
        sources = self._source_names(dedup=True)
        if not sources:
            messagebox.showerror("Loi", "Chua nhap may nguon o tab 'Tao acc'")
            return

        self._login_accounts = accounts
        self._login_sources = sources
        rf.STOP.clear()
        rf.RESUME.set()
        rf.LDCONSOLE = self.var_ld.get()
        rf.CLONES = self.var_clones.get()
        rf.SLOW = self.var_slow.get()

        self._set_config_state("disabled")
        self.btn_start.config(state="disabled")
        self.btn_login_start.config(state="disabled")
        self.worker = threading.Thread(target=self._run_login, daemon=True)
        self.worker.start()

    def _run_login(self):
        log = rf.Log("login")
        try:
            import roblox_login as rl
            console = rf.LDConsole(self.var_ld.get())
            rl.STORE = AccountStore(self.var_db.get())
            log(f"DB: {os.path.abspath(self.var_db.get())} | "
                f"{len(self._login_accounts)} acc can login")
            results = rl.run_login(console, self._login_accounts, self._login_sources,
                                   db=self.var_db.get())
            rf.report(results)
            log("=== xong login ===")
        except Exception as exc:
            log(f"LOI: {type(exc).__name__}: {exc}")

    def _stop_all_ld(self):
        """Tat het may ao LDPlayer (ldconsole quitall). Chay o thread rieng de
        khong dong bang GUI."""
        path = self.var_ld.get()

        def work():
            try:
                rf.LDConsole(path).quit_all()
                rf.Log("main")("Da tat tat ca may ao LDPlayer")
            except Exception as exc:
                rf.Log("main")(f"Tat LD loi: {type(exc).__name__}: {exc}")

        threading.Thread(target=work, daemon=True).start()

    def _build_status(self):
        f = ttk.LabelFrame(self.root, text="Trang thai")
        f.pack(fill="x", padx=8, pady=4)
        self.var_status = tk.StringVar(value="chua chay")
        ttk.Label(f, textvariable=self.var_status, font=("TkDefaultFont", 10)).pack(
            anchor="w", padx=8, pady=4)
        # Thong bao minh bach: cong cu co ghi nhan hoat dong (mo app, so acc) de
        # bao cao nang suat. Giu dong nay de nhan vien biet -- dung/hop le hon.
        ttk.Label(f, text="* Hoat dong (mo app, so acc, thoi luong) duoc ghi nhan "
                          "de bao cao nang suat.",
                  foreground="#888", font=("TkDefaultFont", 8)).pack(
            anchor="w", padx=8, pady=(0, 4))

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
        sources = self._source_names(dedup=True)
        if not sources:
            messagebox.showerror("Loi", "Chua nhap may nguon nao")
            return
        self._sources = sources
        self._save_config()

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
        log = rf.Log("main")
        try:
            console = rf.LDConsole(self.var_ld.get())
            rf.STORE = AccountStore(self.var_db.get())
            log(f"DB: {os.path.abspath(self.var_db.get())} "
                f"({rf.STORE.count()} ban ghi)")
            console.global_setting(fps=30, audio=False, fast_play=True)

            # Goi dung ham ma script dung -> Start chay Y HET python roblox_flow.py
            # (mac dinh: xoa Roblox moi vong, xep cua so, tat may dang chay truoc).
            results = rf.run_farm(console, sources=self._sources)
            rf.report(results)
            log("=== da dung tat ca luong ===")
        except Exception as exc:
            log(f"LOI: {type(exc).__name__}: {exc}")

    def _clear_db(self):
        """Xoa toan bo ban ghi trong accounts.db."""
        if self._running():
            messagebox.showwarning(
                "Dang chay", "Dung farm truoc da -- cac luong dang ghi vao DB.")
            return

        db = self.var_db.get()
        if not os.path.exists(db):
            messagebox.showerror("Loi", f"Khong thay DB:\n{os.path.abspath(db)}")
            return

        st = db_stats(db)
        total, ck = st.get("tong", 0), st.get("cookie", 0)
        if not total:
            messagebox.showinfo("Trong", "DB khong co ban ghi nao de xoa.")
            return

        msg = (f"Xoa toan bo {total} ban ghi trong:\n{os.path.abspath(db)}\n\n"
               f"Khong hoan tac duoc.")
        if ck:
            msg += (f"\n\nCANH BAO: {ck} acc co cookie. Do la credential song -- "
                    f"xoa la mat han, khong lay lai duoc.\nNen bam 'Xuat TXT' truoc.")
        if not messagebox.askyesno("Xac nhan xoa", msg, icon="warning", default="no"):
            return

        # Dong ket noi con mo tu lan chay truoc: VACUUM doi khong con ket noi
        # nao khac dang mo file, khong thi bao 'database is locked'.
        if getattr(rf, "STORE", None) is not None:
            try:
                rf.STORE.close()
            except Exception:
                pass
            rf.STORE = None

        try:
            store = AccountStore(db)
            n = store.clear()
            store.close()
        except Exception as exc:
            messagebox.showerror("Loi", f"{type(exc).__name__}: {exc}")
            return

        rf.Log("main")(f"Da xoa {n} ban ghi khoi {os.path.abspath(db)}")
        self.var_status.set("[dung]  DB trong")
        messagebox.showinfo("Xong", f"Da xoa {n} ban ghi.")

    def _export(self):
        db = self.var_db.get()
        if not os.path.exists(db):
            messagebox.showerror("Loi", f"Khong thay DB:\n{os.path.abspath(db)}")
            return
        out = filedialog.asksaveasfilename(
            title="Luu file txt", defaultextension=".txt",
            initialdir=str(app_dir()), initialfile="acc.txt",
            filetypes=[("Text", "*.txt")])
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
            self.btn_login_start.config(state="normal")
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
        def walk(parent):
            for c in parent.winfo_children():
                try:
                    c.config(state=state)
                except tk.TclError:
                    pass
                walk(c)
        walk(self.config_widgets)
        walk(self.sources_widget)

    def _on_close(self):
        self._save_config()
        if self._running():
            if not messagebox.askyesno(
                    "Thoat", "Cac luong dang chay. Dong app va TAT HET may ao?"):
                return
        # 1. Ghi nhan dong app: da lam duoc bao nhieu acc, chay bao lau.
        st = db_stats(self.var_db.get())
        t_log = telemetry.log(
            "app_close",
            accounts_total=st.get("tong", 0),
            accounts_done=st.get("done", 0),
            accounts_cookie=st.get("cookie", 0),
            created_this_session=st.get("tong", 0) - getattr(self, "_t_baseline", 0),
            duration_sec=int(time.time() - getattr(self, "_t_start", time.time())),
        )
        # 2. Bao cac luong dung (chung la daemon -> chet theo tien trinh, nhung
        #    set STOP de chung khong con gui lenh trong luc dang tat may ao).
        rf.STOP.set()
        rf.RESUME.set()
        # 3. Tat het may ao LDPlayer (ldconsole quitall) truoc khi thoat.
        try:
            rf.LDConsole(self.var_ld.get()).quit_all()
        except Exception:
            pass
        # Cho su kien dong app gui xong (toi da 3s) truoc khi thoat tien trinh.
        if t_log is not None:
            t_log.join(timeout=3)
        self.root.destroy()


def main():
    # License gate (an): phai xac thuc online moi cho mo. Key lay tu config.json
    # neu co, mac dinh "3301".
    from ldauto import license as _lic
    key = load_config().get("license_key", _lic.DEFAULT_KEY)
    if not _lic.check(key):
        try:
            r = tk.Tk()
            r.withdraw()
            messagebox.showerror(
                "Loi", "Khong the ket noi may chu. Vui long kiem tra mang va thu lai.")
            r.destroy()
        except Exception:
            pass
        sys.exit(1)

    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
