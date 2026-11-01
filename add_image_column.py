import sqlite3

conn = sqlite3.connect("smartfind.db")
columns = [row[1] for row in conn.execute("PRAGMA table_info(items)")]

if "image" in columns:
    print("image column already exists")
else:
    conn.execute("ALTER TABLE items ADD COLUMN image TEXT")
    conn.commit()
    print("image column added")

conn.close()