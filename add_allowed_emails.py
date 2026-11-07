import os
import sqlite3
import sys

conn = sqlite3.connect("smartfind.db")
conn.execute(
    "CREATE TABLE IF NOT EXISTS allowed_emails "
    "(email TEXT PRIMARY KEY, added_at TEXT DEFAULT CURRENT_TIMESTAMP)"
)

# Emails typed after the script name, e.g. python add_allowed_emails.py a@x.com b@x.com
emails = [e.strip().lower() for e in sys.argv[1:]]

# Emails from optional text files (one email per line)
for filename in ("admin.txt", "allowed_emails.txt"):
    if os.path.exists(filename):
        with open(filename) as f:
            emails += [line.strip().lower() for line in f if line.strip()]

# Everyone who already has an account stays on the list
emails += [row[0] for row in conn.execute("SELECT email FROM users")]

added = 0
for email in set(emails):
    if "@" not in email:
        continue
    added += conn.execute(
        "INSERT OR IGNORE INTO allowed_emails (email) VALUES (?)", (email,)
    ).rowcount

conn.commit()
print("newly added:", added)
print("allowed list:", [r[0] for r in conn.execute("SELECT email FROM allowed_emails ORDER BY email")])
conn.close()