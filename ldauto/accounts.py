"""Kho tai khoan: sinh username/password ngau nhien va luu vao mot file SQLite.

SQLite dong vai tro nhu LiteDB ben .NET -- CSDL nhung, mot file, khong server,
va nam san trong thu vien chuan Python nen khong them dependency nao.

An toan cho nhieu thread: moi thread trong run_parallel goi new_account() cua
rieng no, va ten phai la duy nhat tren toan bo kho.
"""

from __future__ import annotations

import secrets
import sqlite3
import string
import threading
import time
from dataclasses import dataclass
from pathlib import Path

# Username Roblox: 3-20 ky tu, chi chu/so/mot dau gach duoi, khong duoc bat dau
# hoac ket thuc bang gach duoi.
# Ten sinh ra co dang <TinhTu><DanhTu><so><vai chu>, vi du "BraveTiger4821mz":
# phan dau doc len co nghia nhu ten nguoi that dat, phan so + chu ngau nhien o
# duoi de khong trung ten da co tren Roblox.
#   - Moi tu dai toi da 6 chu -> ten dai nhat 6+6+4+3 = 19, khong vuot 20.
#   - Phan chu o duoi chi dung PHU AM: khong co nguyen am thi khong vo tinh
#     ghep thanh tu tuc -- thu ma Roblox tu choi.
#   - Them tu moi thi giu <= 6 chu va tranh tu nhay cam.
_U_ADJ = (
    "Happy", "Brave", "Swift", "Lucky", "Sunny", "Clever", "Mighty", "Silent",
    "Golden", "Cosmic", "Frozen", "Tiny", "Wild", "Cool", "Epic", "Funny",
    "Sleepy", "Quick", "Calm", "Bright", "Fuzzy", "Jolly", "Noble", "Royal",
    "Rapid", "Shiny", "Smart", "Super", "Turbo", "Mega", "Hyper", "Magic",
    "Mystic", "Lunar", "Solar", "Atomic", "Blue", "Red", "Green", "Pink",
    "Silver", "Icy", "Fiery", "Stormy", "Windy", "Sneaky", "Chill", "Fancy",
    "Gentle", "Humble", "Proud", "Bold",
)
_U_NOUN = (
    "Tiger", "Panda", "Wolf", "Eagle", "Dragon", "Ninja", "Falcon", "Rabbit",
    "Otter", "Koala", "Shark", "Lion", "Bear", "Fox", "Hawk", "Robot",
    "Wizard", "Pirate", "Rocket", "Comet", "Storm", "Pixel", "Gamer",
    "Racer", "Hunter", "Ranger", "Viking", "Turtle", "Monkey", "Parrot",
    "Whale", "Zebra", "Llama", "Moose", "Bison", "Cobra", "Raven", "Owl",
    "Lynx", "Puma", "Gecko", "Badger", "Kitten", "Puppy", "Bunny", "Hero",
    "Pilot", "Scout", "Chef", "Rider", "Player", "Miner", "Farmer", "Archer",
    "Golem", "Star", "Moon", "Planet", "Galaxy", "Nebula", "Meteor",
    "Blaze", "Frost", "Flame", "Wave", "River", "Stone", "Cloud", "Breeze",
)
# Bo k, x, t, g: thieu chung thi khong ghep duoc may kieu viet tat tuc
# (fck, sht, kkk, xxx...).
_U_TAIL = "bcdfhjmnpqrsvwz"                       # phu am, chu thuong

# Password chi dung chu-so co CHU Y: `adb shell input text` nuot mot loat ky tu
# dac biet. Instance.text() co escape, nhung mat khau la thu ma go sai mot ky tu
# la hong ca tai khoan mà khong bao loi gi -- nen bo han rui ro do.
# Roblox chi doi toi thieu 8 ky tu, 16 ky tu chu-so da qua du.
_P_CHARS = string.ascii_letters + string.digits

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT    NOT NULL UNIQUE,
    password   TEXT    NOT NULL,
    ld_index   INTEGER,
    gender     TEXT,
    status     TEXT    NOT NULL DEFAULT 'new',
    note       TEXT,
    cookie          TEXT,           -- .ROBLOSECURITY, credential song
    roblox_user_id  INTEGER,        -- id that tu API, xac nhan cookie dung acc
    verified_at     REAL,           -- luc verify cookie qua API
    created_at REAL    NOT NULL,
    updated_at REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status);
"""


@dataclass
class Account:
    username: str
    password: str
    ld_index: int | None = None
    gender: str | None = None
    status: str = "new"


def random_username(length: int = 20) -> str:
    """Ten co nghia + so + vai chu ngau nhien, dai toi da `length` ky tu."""
    name = (
        secrets.choice(_U_ADJ) + secrets.choice(_U_NOUN)
        + str(10 + secrets.randbelow(9990))                    # so 2-4 chu so
        + "".join(secrets.choice(_U_TAIL)                      # 2-3 chu ngau nhien
                  for _ in range(2 + secrets.randbelow(2)))
    )
    return name[:length]


def random_password(length: int = 16, avoid: str | None = None) -> str:
    """Bao dam co ca chu hoa, chu thuong va so -- khong phu thuoc may rui.

    Rut ngau nhien roi 'hy vong co du ca ba loai' la sai: xac suat thieu mot
    loai khong phai 0, va khi no xay ra thi Roblox tu choi mat khau ma script
    khong biet vi sao.

    Man tao mat khau cua Roblox doi ba dieu, doc duoc tren chinh man hinh:
        - Is not a simple password      -> 16 ky tu ngau nhien, khong lo
        - Is at least 8 characters long -> ep length >= 8
        - Does not match username       -> truyen username vao `avoid`

    `avoid` loai ca hai chieu chua nhau, khong chi bang nhau: Roblox coi mat
    khau chua nguyen username la 'match'.
    """
    if length < 8:
        # Roblox doi toi thieu 8. Chan tu day chu khong de no truot xuong
        # toi man hinh roi bao do -- luc do script khong biet vi sao.
        raise ValueError("Roblox doi mat khau toi thieu 8 ky tu")
    for _ in range(50):
        picks = [
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.digits),
        ]
        picks += [secrets.choice(_P_CHARS) for _ in range(length - len(picks))]
        # Xao tron bang secrets, khong dung random.shuffle: random dung Mersenne
        # Twister, doan duoc trang thai neu biet du output.
        for i in range(len(picks) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            picks[i], picks[j] = picks[j], picks[i]
        pw = "".join(picks)
        if avoid:
            a, b = pw.lower(), avoid.lower()
            if a == b or b in a or a in b:
                continue
        return pw
    raise RuntimeError("Khong sinh duoc mat khau khac username")


class AccountStore:
    """Mot file SQLite giu moi tai khoan da sinh."""

    def __init__(self, path: str | Path = "accounts.db"):
        self.path = Path(path)
        # check_same_thread=False: run_parallel chay nhieu thread tren cung mot
        # ket noi. Moi cau lenh deu nam trong self._lock nen khong co hai cau
        # nao chay chong nhau.
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(_SCHEMA)
            # Them cot moi vao DB cu (tao truoc khi co cookie) neu con thieu.
            have = {r["name"] for r in self._db.execute("PRAGMA table_info(accounts)")}
            for col, decl in (("cookie", "TEXT"),
                              ("roblox_user_id", "INTEGER"),
                              ("verified_at", "REAL")):
                if col not in have:
                    self._db.execute(f"ALTER TABLE accounts ADD COLUMN {col} {decl}")
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ---------- ghi ----------

    def new_account(
        self,
        ld_index: int | None = None,
        username_len: int = 20,
        password_len: int = 16,
        tries: int = 20,
    ) -> Account:
        """Sinh mot cap username/password chua tung co, luu lai roi tra ve.

        Cot username co rang buoc UNIQUE, nen chinh CSDL la trong tai quyet dinh
        trung hay khong -- khong phai mot phep kiem tra roi moi ghi, vi giua hai
        buoc do thread khac co the chen vao.
        """
        now = time.time()
        for _ in range(tries):
            uname = random_username(username_len)
            acc = Account(uname, random_password(password_len, avoid=uname), ld_index)
            try:
                with self._lock:
                    self._db.execute(
                        "INSERT INTO accounts (username, password, ld_index, "
                        "status, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                        (acc.username, acc.password, ld_index, "new", now, now),
                    )
                    self._db.commit()
                return acc
            except sqlite3.IntegrityError:
                continue  # trung ten (gan nhu khong bao gio) -> sinh lai
        raise RuntimeError(f"Khong sinh duoc username duy nhat sau {tries} lan")

    def add(self, username: str, password: str, ld_index: int | None = None,
            status: str = "new") -> None:
        """Them mot cap user:pass CHO SAN (vd danh sach login). Da co thi cap nhat
        mat khau + reset ld_index, khong tao trung.

        Dung cho luong login: input la user:pass co truoc, khong sinh ngau nhien.
        """
        now = time.time()
        with self._lock:
            self._db.execute(
                "INSERT INTO accounts (username, password, ld_index, status, "
                "created_at, updated_at) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(username) DO UPDATE SET password=excluded.password, "
                "ld_index=excluded.ld_index, updated_at=excluded.updated_at",
                (username, password, ld_index, status, now, now),
            )
            self._db.commit()

    def update(self, username: str, **fields) -> None:
        """Cap nhat status / gender / note / ld_index cua mot tai khoan."""
        allowed = {"status", "gender", "note", "ld_index", "password",
                   "cookie", "roblox_user_id", "verified_at"}
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"Cot khong hop le: {sorted(bad)}")
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._lock:
            self._db.execute(
                f"UPDATE accounts SET {cols}, updated_at=? WHERE username=?",
                (*fields.values(), time.time(), username),
            )
            self._db.commit()

    # ---------- doc ----------

    def delete(self, username: str) -> None:
        """Xoa han mot ban ghi. Dung khi acc coi nhu chua tao duoc."""
        with self._lock:
            self._db.execute("DELETE FROM accounts WHERE username=?", (username,))
            self._db.commit()

    def clear(self) -> int:
        """Xoa MOI ban ghi, tra ve so ban ghi da xoa.

        KHONG hoan tac duoc. Acc co cookie la credential song -- xuat ra file
        truoc khi goi cai nay, mat roi la mat han.

        VACUUM sau khi xoa: DELETE khong tra lai dung luong cho o dia, file
        .db van giu nguyen kich thuoc cu. VACUUM phai chay NGOAI transaction
        nen goi sau commit.
        """
        with self._lock:
            n = self._db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
            self._db.execute("DELETE FROM accounts")
            self._db.commit()
            self._db.execute("VACUUM")
            self._db.commit()
        return n

    def get(self, username: str) -> sqlite3.Row | None:
        with self._lock:
            cur = self._db.execute(
                "SELECT * FROM accounts WHERE username=?", (username,))
            return cur.fetchone()

    def all(self, status: str | None = None) -> list[sqlite3.Row]:
        q = "SELECT * FROM accounts"
        args: tuple = ()
        if status:
            q += " WHERE status=?"
            args = (status,)
        q += " ORDER BY id"
        with self._lock:
            return self._db.execute(q, args).fetchall()

    def count(self, status: str | None = None) -> int:
        return len(self.all(status))


def _main() -> int:
    """Xem kho tai khoan:  python -m ldauto.accounts [file.db] [status]"""
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "accounts.db"
    status = sys.argv[2] if len(sys.argv) > 2 else None
    store = AccountStore(path)
    rows = store.all(status)
    print(f"{path}: {len(rows)} tai khoan" + (f" (status={status})" if status else ""))
    print(f"{'id':>4}  {'username':22} {'password':18} {'idx':>3} "
          f"{'gender':7} {'status':11} {'cookie':8} note")
    for r in rows:
        t = time.strftime("%H:%M:%S", time.localtime(r["created_at"]))
        ck = r["cookie"] if "cookie" in r.keys() else None
        ck_mark = f"{len(ck)}c" if ck else "-"
        print(f"{r['id']:>4}  {r['username']:22} {r['password']:18} "
              f"{str(r['ld_index'] if r['ld_index'] is not None else '-'):>3} "
              f"{r['gender'] or '-':7} {r['status']:11} {ck_mark:8} {r['note'] or ''} ({t})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
