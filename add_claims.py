import sqlite3

conn = sqlite3.connect("smartfind.db")
cur = conn.cursor()

item_cols = [r[1] for r in cur.execute("PRAGMA table_info(items)")]
for name, sql in [
    ("private_question", "ALTER TABLE items ADD COLUMN private_question TEXT"),
    ("at_security", "ALTER TABLE items ADD COLUMN at_security INTEGER DEFAULT 0"),
]:
    if name in item_cols:
        print(name, "already exists")
    else:
        cur.execute(sql)
        print(name, "added")

cur.execute("""
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    claimant_id INTEGER NOT NULL,
    answer TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    proof_request TEXT,
    proof_text TEXT,
    proof_image TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    decided_at TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    claim_id INTEGER,
    user_id INTEGER,
    action TEXT NOT NULL,
    detail TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
print("tables:", [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")])
conn.close()