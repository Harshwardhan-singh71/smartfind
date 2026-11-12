import sqlite3

conn = sqlite3.connect("smartfind.db")
columns = [row[1] for row in conn.execute("PRAGMA table_info(items)")]
if "serial_number" not in columns:
    conn.execute("ALTER TABLE items ADD COLUMN serial_number TEXT")
    conn.commit()
    print("Added items.serial_number")
else:
    print("items.serial_number already exists")
conn.close()