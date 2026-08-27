"""Purge all PII: screening records + uploaded images (rules.md §1.4).

Run:  python backend/purge.py
Asks for confirmation before deleting anything.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR.parent / "screenings.db"
UPLOADS_DIR = BASE_DIR / "uploads"


def main() -> None:
    uploads = [p for p in UPLOADS_DIR.glob("*") if p.is_file() and p.name != ".gitkeep"]
    db_rows = 0
    if DB_PATH.exists():
        import sqlite3
        with sqlite3.connect(DB_PATH) as conn:
            db_rows = conn.execute("SELECT COUNT(*) FROM screenings").fetchone()[0]

    print(f"Screening records in database : {db_rows}")
    print(f"Uploaded document images      : {len(uploads)}")
    if db_rows == 0 and not uploads:
        print("Nothing to purge.")
        return

    answer = input("Delete ALL records and images? Type PURGE to confirm: ").strip()
    if answer != "PURGE":
        print("Aborted — nothing deleted.")
        return

    if db_rows:
        import sqlite3
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM screenings")
        print(f"Deleted {db_rows} screening records.")

    removed = 0
    for path in uploads:
        try:
            path.unlink()
            removed += 1
        except OSError as exc:
            print(f"Could not delete {path.name}: {exc}")
    print(f"Deleted {removed} uploaded images.")
    print("PII purge complete.")


if __name__ == "__main__":
    main()
