r"""Test AI limits and the circuit breaker (the gentler pause) in ai.py.

Run:  D:\PYTHON\python.exe test_ai_limits.py
Uses a TEMPORARY database. Never calls the real Gemini: the Gemini client is replaced by a fake.
Every check here FAILS when the feature it tests is missing.
"""
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest.mock as mock

HERE = os.path.dirname(os.path.abspath(__file__))
SETUP = ["init_db.py", "add_users.py", "migrate_places.py", "add_image_column.py",
         "add_claims.py", "add_must_change.py", "add_notifications.py",
         "add_match_alerts.py", "add_messages.py", "add_phone_calls.py",
         "add_item_details.py", "add_post_reports.py", "add_ai_usage.py"]

tmp = tempfile.mkdtemp(prefix="smartfind_test_ai_limits_")
os.chdir(tmp)
for s in SETUP:
    done = subprocess.run([sys.executable, os.path.join(HERE, s)], cwd=tmp,
                          capture_output=True, text=True)
    if done.returncode != 0:
        print("SETUP FAILED:", s, done.stderr[-300:])
        os.chdir(HERE)
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(1)

# A fake key, so ai.is_available() is the REAL function (it must see the key and the pause).
os.environ["GEMINI_API_KEY"] = "test-key-not-real"
sys.path.insert(0, HERE)
import ai  # noqa: E402

results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + name)


def db():
    conn = sqlite3.connect("smartfind.db")
    conn.row_factory = sqlite3.Row
    return conn


def add_user(name, email):
    from werkzeug.security import generate_password_hash
    conn = db()
    conn.execute("INSERT INTO users (name, email, password_hash, must_change_password) VALUES (?,?,?,0)",
                 (name, email, generate_password_hash("Test@12345")))
    conn.commit()
    uid = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
    conn.close()
    return uid


alice = add_user("Alice", "alice@test.com")
bob = add_user("Bob", "bob@test.com")

# ---------- 1. site-wide budget and per-user limit ----------
conn = db()
conn.execute("INSERT OR REPLACE INTO ai_usage (user_id, day, used) VALUES (0, date('now'), ?)",
             (ai.GLOBAL_DAILY_LIMIT,))
conn.execute("INSERT OR REPLACE INTO ai_usage (user_id, day, used) VALUES (?, date('now'), 0)", (alice,))
conn.commit()
ok = ai.allow_use(conn, alice)
conn.close()
check("global budget used up blocks a user", ok is False)

conn = db()
conn.execute("INSERT OR REPLACE INTO ai_usage (user_id, day, used) VALUES (0, date('now'), 5)")
conn.execute("INSERT OR REPLACE INTO ai_usage (user_id, day, used) VALUES (?, date('now'), 5)", (alice,))
conn.commit()
ai.refund_use(conn, alice)
conn.close()
conn = db()
uu = conn.execute("SELECT used FROM ai_usage WHERE user_id = ? AND day = date('now')", (alice,)).fetchone()[0]
gu = conn.execute("SELECT used FROM ai_usage WHERE user_id = 0 AND day = date('now')").fetchone()[0]
conn.close()
check("refund gives back the user's and the site-wide count", uu == 4 and gu == 4)

conn = db()
conn.execute("INSERT OR REPLACE INTO ai_usage (user_id, day, used) VALUES (0, date('now'), 0)")
conn.execute("INSERT OR REPLACE INTO ai_usage (user_id, day, used) VALUES (?, date('now'), ?)",
             (alice, ai.DAILY_LIMIT))
conn.execute("INSERT OR REPLACE INTO ai_usage (user_id, day, used) VALUES (?, date('now'), 0)", (bob,))
conn.commit()
ok_alice = ai.allow_use(conn, alice)
ok_bob = ai.allow_use(conn, bob)
conn.close()
check("per-user limit stops only that user", ok_alice is False and ok_bob is True)

# ---------- 2. circuit breaker ----------
class Reply:          # a fake successful Gemini answer
    text = "ok"


def timeout():
    return TimeoutError("The read operation timed out")


def reset():
    ai._consecutive_failures = 0
    ai._cb_until = 0.0
    ai._paused_until = 0.0


def run(errors_or_replies, times):
    """Call ask_text(fast=True) `times` times against a fake Gemini client.
    Returns (results, how many times the fake Gemini was really called)."""
    client = mock.MagicMock()
    client.models.generate_content.side_effect = errors_or_replies
    out = []
    with mock.patch.object(ai, "_get_client", return_value=client), \
            mock.patch.object(ai.time, "sleep"):
        for _ in range(times):
            out.append(ai.ask_text("test", fast=True))
    return out, client.models.generate_content.call_count


reset()
check("the AI is available at the start", ai.is_available() is True)

reset()
run([timeout()], 1)
check("one timeout does not pause the AI", ai.is_available() is True)

reset()
run([timeout(), timeout()], 2)
check("two timeouts in a row pause the AI", ai.is_available() is False)

reset()
run([timeout(), timeout()], 2)
out, calls = run([Reply()], 1)
check("while paused, Gemini is not called at all", calls == 0 and out == [None])

reset()
run([timeout(), Reply(), timeout()], 3)
check("a success in between resets the count (fail, ok, fail does not pause)", ai.is_available() is True)

reset()
run([timeout(), timeout()], 2)
real_now = time.time()
with mock.patch.object(ai.time, "time", return_value=real_now + ai.BREAKER_PAUSE + 1):
    back = ai.is_available()
check("the AI is available again after the pause", back is True)

reset()
check("the pause is about 30 seconds", ai.BREAKER_PAUSE == 30)

os.chdir(HERE)
shutil.rmtree(tmp, ignore_errors=True)
print()
if all(results):
    print(f"ALL {len(results)} CHECKS PASSED")
    sys.exit(0)
print(f"{results.count(False)} OF {len(results)} CHECKS FAILED")
sys.exit(1)
