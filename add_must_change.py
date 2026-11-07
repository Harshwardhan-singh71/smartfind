import sqlite3

conn = sqlite3.connect("smartfind.db")
cols = [r[1] for r in conn.execute("PRAGMA table_info(users)")]
if "must_change_password" in cols:
    print("already exists")
else:
    conn.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0")
    conn.commit()
    print("must_change_password added")
conn.close()