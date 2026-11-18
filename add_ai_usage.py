import sqlite3

conn = sqlite3.connect("smartfind.db")
conn.execute("""
CREATE TABLE IF NOT EXISTS ai_usage (
    user_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
)
""")
conn.commit()
conn.close()
print("ai_usage table ready")
