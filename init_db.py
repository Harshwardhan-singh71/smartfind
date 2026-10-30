import sqlite3

conn = sqlite3.connect("smartfind.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    location TEXT,
    status TEXT NOT NULL CHECK (status IN ('lost', 'found')),
    contact_name TEXT,
    contact_email TEXT,
    date_reported TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

sample_items = [
    ("Black wallet", "Leather wallet with ID card inside", "Wallet", "Library", "lost", "Rahul", "rahul@example.com"),
    ("Blue water bottle", "Milton bottle with a sticker on it", "Bottle", "Canteen", "found", "Priya", "priya@example.com"),
    ("Scientific calculator", "Casio fx-991EX", "Electronics", "Block 2, Room 204", "lost", "Aman", "aman@example.com"),
]

cur.executemany(
    "INSERT INTO items (title, description, category, location, status, contact_name, contact_email) VALUES (?, ?, ?, ?, ?, ?, ?)",
    sample_items,
)

conn.commit()

for row in cur.execute("SELECT id, title, status, location FROM items"):
    print(row)

conn.close()