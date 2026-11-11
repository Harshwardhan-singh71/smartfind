import sqlite3

conn = sqlite3.connect("smartfind.db")
conn.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    body TEXT,
    file_name TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()
conn.close()
print("messages table ready")