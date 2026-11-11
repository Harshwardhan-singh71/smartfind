import sqlite3

conn = sqlite3.connect("smartfind.db")
conn.execute("""
CREATE TABLE IF NOT EXISTS match_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    lost_item_id INTEGER NOT NULL,
    found_item_id INTEGER NOT NULL,
    dismissed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (lost_item_id, found_item_id)
)
""")
conn.commit()
conn.close()
print("match_alerts table ready")