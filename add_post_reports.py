import sqlite3

conn = sqlite3.connect("smartfind.db")
conn.execute(
    "CREATE TABLE IF NOT EXISTS post_reports ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "item_id INTEGER NOT NULL, "
    "reporter_id INTEGER NOT NULL, "
    "reason TEXT NOT NULL, "
    "note TEXT, "
    "status TEXT NOT NULL DEFAULT 'open', "
    "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
    "UNIQUE (item_id, reporter_id))"
)
conn.commit()
conn.close()
print("post_reports table is ready")