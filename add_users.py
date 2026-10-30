import sqlite3

conn = sqlite3.connect("smartfind.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

try:
    cur.execute("ALTER TABLE items ADD COLUMN user_id INTEGER")
except sqlite3.OperationalError:
    print("user_id column already exists")

conn.commit()

print("users columns:", [row[1] for row in cur.execute("PRAGMA table_info(users)")])
print("items columns:", [row[1] for row in cur.execute("PRAGMA table_info(items)")])

conn.close()