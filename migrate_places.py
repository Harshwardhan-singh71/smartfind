import shutil
import sqlite3
from datetime import datetime

DB = "smartfind.db"

conn = sqlite3.connect(DB)
old_cols = [row[1] for row in conn.execute("PRAGMA table_info(items)")]
conn.close()

if "place" in old_cols:
    print("Already upgraded. Nothing to do.")
    raise SystemExit

backup = datetime.now().strftime("smartfind_backup_%Y%m%d_%H%M%S.db")
shutil.copy(DB, backup)
print("Backup saved as", backup)

conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute("""
CREATE TABLE items_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    location TEXT,
    status TEXT NOT NULL CHECK (status IN ('lost', 'found', 'seen')),
    contact_name TEXT,
    contact_email TEXT,
    date_reported TEXT DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    resolved INTEGER DEFAULT 0,
    place TEXT,
    place_details TEXT,
    event_date TEXT,
    event_time TEXT
)
""")

base = ("id, title, description, category, location, status, contact_name, "
        "contact_email, date_reported, user_id, resolved")

cur.execute(f"INSERT INTO items_new ({base}) SELECT {base} FROM items")

cur.execute("DROP TABLE items")
cur.execute("ALTER TABLE items_new RENAME TO items")
conn.commit()

print("items columns:", [row[1] for row in cur.execute("PRAGMA table_info(items)")])
print("rows kept:", cur.execute("SELECT COUNT(*) FROM items").fetchone()[0])
conn.close()