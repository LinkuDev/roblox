"""Xuat user:pass:cookie ra file txt. Doc thang accounts.db, khong can ldauto.

    python examples/xuat_txt.py                        # accounts.db -> acc.txt
    python examples/xuat_txt.py accounts.db acc.txt    # chi ro file
    python examples/xuat_txt.py --all                  # xuat ca acc chua co cookie
"""

import os
import sqlite3
import sys

WARNING = ("_|WARNING:-DO-NOT-SHARE-THIS.--Sharing-this-will-allow-someone-to-"
           "log-into-your-account-and-steal-your-points-and-Robux|_")


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--all"]
    xuat_het = "--all" in sys.argv[1:]
    db = args[0] if len(args) > 0 else "accounts.db"
    out = args[1] if len(args) > 1 else "acc.txt"

    if not os.path.exists(db):
        print(f"[!] Khong thay file DB: {os.path.abspath(db)}")
        print("    accounts.db duoc tao boi roblox_flow.py o THU MUC ban chay lenh do.")
        print("    Tim no tren Windows:   dir /s /b accounts.db")
        print("    Roi chi ro:            python examples\\xuat_txt.py <duong_dan_day_du> acc.txt")
        return 1

    print(f"Doc DB: {os.path.abspath(db)}")
    # mode=rw (uri): KHONG tu tao DB rong neu path sai -- de loi ro rang.
    con = sqlite3.connect(f"file:{db}?mode=rw", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT username, password, cookie FROM accounts ORDER BY id").fetchall()
    except sqlite3.OperationalError as e:
        print(f"[!] Doc bang 'accounts' that bai: {e}")
        print("    File nay khong phai accounts.db cua roblox_flow (thieu bang).")
        return 1
    finally:
        con.close()

    lines = []
    bo_qua = 0
    for r in rows:
        ck = r["cookie"] or ""
        if not ck and not xuat_het:
            bo_qua += 1
            continue
        # Bao dam cookie co tien to WARNING de dan thang vao trinh duyet duoc.
        if ck and not ck.startswith("_|WARNING"):
            ck = WARNING + ck
        lines.append(f"{r['username']}:{r['password']}:{ck}")

    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))

    print(f"Da xuat {len(lines)} acc -> {out}")
    if bo_qua:
        print(f"Bo qua {bo_qua} acc chua co cookie (--all de xuat het)")
    print("LUU Y: file chua cookie = credential song, dung commit/gui bua bai.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
