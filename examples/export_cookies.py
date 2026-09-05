"""Xuat tai khoan + cookie tu accounts.db ra file.

    python examples/export_cookies.py                       # user:pass:cookie -> accounts_export.txt
    python examples/export_cookies.py --format json -o out.json
    python examples/export_cookies.py --per-account cookies/   # moi acc mot file
    python examples/export_cookies.py --status done            # chi acc da xong

Mac dinh chi xuat acc CO cookie. Dung --all de xuat het (ke ca failed).
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ldauto import AccountStore  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="accounts.db")
    ap.add_argument("-o", "--out", default="accounts_export.txt")
    ap.add_argument("--format", choices=["combo", "json", "csv"], default="combo",
                    help="combo = user:pass:cookie moi dong (mac dinh)")
    ap.add_argument("--status", default=None, help="chi xuat acc co status nay")
    ap.add_argument("--all", action="store_true",
                    help="xuat ca acc chua co cookie (mac dinh chi acc co cookie)")
    ap.add_argument("--per-account", metavar="DIR",
                    help="ghi moi acc mot file <username>.txt trong DIR")
    args = ap.parse_args()

    store = AccountStore(args.db)
    rows = store.all(args.status)
    if not args.all:
        rows = [r for r in rows if r["cookie"]]

    if not rows:
        print("Khong co acc nao de xuat"
              + ("" if args.all else " (chua acc nao co cookie -- them --all de xuat het)"))
        return 1

    # Moi acc mot file rieng
    if args.per_account:
        d = Path(args.per_account)
        d.mkdir(parents=True, exist_ok=True)
        for r in rows:
            (d / f"{r['username']}.txt").write_text(
                f"{r['username']}:{r['password']}:{r['cookie'] or ''}\n",
                encoding="utf-8")
        print(f"Da ghi {len(rows)} file vao {d}/")
        return 0

    out = Path(args.out)
    if args.format == "combo":
        out.write_text(
            "".join(f"{r['username']}:{r['password']}:{r['cookie'] or ''}\n" for r in rows),
            encoding="utf-8")
    elif args.format == "json":
        out.write_text(json.dumps([{
            "username": r["username"], "password": r["password"],
            "cookie": r["cookie"], "roblox_user_id": r["roblox_user_id"],
            "status": r["status"],
        } for r in rows], indent=2, ensure_ascii=False), encoding="utf-8")
    elif args.format == "csv":
        import csv
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["username", "password", "cookie", "roblox_user_id", "status"])
            for r in rows:
                w.writerow([r["username"], r["password"], r["cookie"],
                            r["roblox_user_id"], r["status"]])

    print(f"Da xuat {len(rows)} acc -> {out} ({args.format})")
    print("LUU Y: file nay chua cookie = credential song, dung commit/gui bua bai.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
