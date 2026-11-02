import sqlite3

conn = sqlite3.connect("smartfind.db")
cur = conn.cursor()

already = cur.execute(
    "SELECT COUNT(*) FROM items WHERE contact_email LIKE '%@demo.smartfind'"
).fetchone()[0]
if already:
    print("Demo items already added. Nothing to do.")
    raise SystemExit

demo_items = [
    ("Blue steel water bottle", "Blue steel bottle with a small sticker on the side", "Bottle",
     "Canteen", "found", "Demo Student", "demo1@demo.smartfind", "Canteen", "", "2026-11-01", "13:00"),
    ("Blue water bottle", "Blue Milton bottle with a sticker, lost near the parking area", "Bottle",
     "Parking, near the gate", "lost", "Demo Student", "demo2@demo.smartfind", "Parking", "near the gate", "2026-11-01", "12:30"),
    ("Black leather wallet", "Black wallet with a few cards and some cash", "Wallet",
     "Library, ground floor", "lost", "Demo Student", "demo3@demo.smartfind", "Library", "ground floor", "2026-11-01", "11:00"),
    ("Casio scientific calculator", "Casio fx-991EX with a name sticker on the back", "Electronics",
     "Lab 3", "found", "Demo Student", "demo4@demo.smartfind", "Lab", "3", "2026-11-01", "15:00"),
    ("Set of keys", "Three keys on a red keychain", "Keys",
     "Cricket Ground, near the pavilion", "seen", "Demo Student", "demo5@demo.smartfind", "Cricket Ground", "near the pavilion", "2026-11-01", "17:00"),
]

cur.executemany(
    "INSERT INTO items (title, description, category, location, status, contact_name, "
    "contact_email, place, place_details, event_date, event_time) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    demo_items,
)
conn.commit()
print("Added", len(demo_items), "demo items")
conn.close()