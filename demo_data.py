"""Demo data for hosts where the database starts empty (like Vercel).

Called from app.py only when running on Vercel. It never runs on your laptop.
Student demo accounts use the SMARTFIND_DEMO_PASSWORD environment variable.
The admin account uses SMARTFIND_ADMIN_PASSWORD (if it is not set, it falls back to
the demo password).
"""
import os
import sqlite3
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

DEFAULT_PASSWORD = "SmartFind@2026"


def seed_if_empty():
    conn = sqlite3.connect("smartfind.db")
    try:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return False

        # init_db.py adds a few owner-less sample posts; the demo uses its own.
        conn.execute("DELETE FROM items WHERE user_id IS NULL")

        password = os.environ.get("SMARTFIND_DEMO_PASSWORD", DEFAULT_PASSWORD)
        pw_hash = generate_password_hash(password)
        admin_password = os.environ.get("SMARTFIND_ADMIN_PASSWORD") or password
        admin_hash = generate_password_hash(admin_password)

        people = [
            ("Aarav (demo)", "aarav@demo.smartfind", "9000000001"),
            ("Meera (demo)", "meera@demo.smartfind", "9000000002"),
        ]
        admin_email = os.environ.get("SMARTFIND_ADMIN_EMAIL", "").strip().lower()
        if admin_email:
            people.append(("Admin", admin_email, None))

        ids = {}
        for name, email, phone in people:
            is_admin = bool(admin_email) and email == admin_email
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash, must_change_password, phone) "
                "VALUES (?, ?, ?, 0, ?)",
                (name, email, admin_hash if is_admin else pw_hash, phone),
            )
            ids[email] = cur.lastrowid

        aarav, meera = ids["aarav@demo.smartfind"], ids["meera@demo.smartfind"]
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        two_days = (date.today() - timedelta(days=2)).isoformat()

        # (title, description, category, status, place, details, date, time, owner, question, at_security)
        items = [
            ("Blue steel water bottle", "Blue steel bottle with a small sticker on the side",
             "Bottle", "found", "Canteen", "", yesterday, "13:00", aarav,
             "What sticker is on the bottle?", 0),
            ("Blue water bottle", "Blue Milton bottle with a sticker, lost near the parking area",
             "Bottle", "lost", "Parking", "near the gate", yesterday, "12:30", meera, None, 0),
            ("Black leather wallet", "Black wallet with a few cards and some cash",
             "Wallet", "lost", "Library", "ground floor", two_days, "11:00", meera, None, 0),
            ("Casio scientific calculator", "Casio fx-991EX with a name sticker on the back",
             "Electronics", "found", "Lab", "Lab 3", yesterday, "15:00", aarav, None, 1),
            ("Set of keys", "Three keys on a red keychain",
             "Keys", "seen", "Cricket Ground", "near the pavilion", yesterday, "17:00", meera, None, 0),
        ]
        for (title, desc, cat, status, place, details, day, hhmm, owner, question, security) in items:
            location = f"{place}, {details}" if details else place
            owner_email = "aarav@demo.smartfind" if owner == aarav else "meera@demo.smartfind"
            owner_name = "Aarav (demo)" if owner == aarav else "Meera (demo)"
            conn.execute(
                "INSERT INTO items (title, description, category, location, status, "
                "contact_name, contact_email, user_id, place, place_details, "
                "event_date, event_time, private_question, at_security) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (title, desc, cat, location, status, owner_name, owner_email, owner,
                 place, details, day, hhmm, question, security),
            )
        conn.commit()
        return True
    finally:
        conn.close()
