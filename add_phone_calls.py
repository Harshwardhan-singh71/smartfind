import sqlite3

conn = sqlite3.connect("smartfind.db")

# 1. users.phone
user_cols = [r[1] for r in conn.execute("PRAGMA table_info(users)")]
if "phone" in user_cols:
    print("users.phone already exists")
else:
    conn.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    print("users.phone added")

# 2. claims.anonymous
claim_cols = [r[1] for r in conn.execute("PRAGMA table_info(claims)")]
if "anonymous" in claim_cols:
    print("claims.anonymous already exists")
else:
    conn.execute("ALTER TABLE claims ADD COLUMN anonymous INTEGER NOT NULL DEFAULT 0")
    print("claims.anonymous added")

# 3. call_consent table
conn.execute("""
CREATE TABLE IF NOT EXISTS call_consent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (claim_id, user_id)
)
""")
conn.commit()
conn.close()
print("call_consent table ready")
