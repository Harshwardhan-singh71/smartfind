import sqlite3

conn = sqlite3.connect("smartfind.db")
conn.execute(
    "CREATE TABLE IF NOT EXISTS item_details ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "item_id INTEGER NOT NULL, "
    "label TEXT NOT NULL, "
    "value TEXT NOT NULL, "
    "FOREIGN KEY (item_id) REFERENCES items(id))"
)
conn.commit()
conn.close()
print("item_details table is ready")