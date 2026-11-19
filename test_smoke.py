"""Smoke test for SmartFind.
Run:  D:\\PYTHON\\python.exe test_smoke.py
Uses a TEMPORARY database. It never touches your real smartfind.db.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SETUP = [
    "init_db.py", "add_users.py", "migrate_places.py", "add_image_column.py",
    "add_claims.py", "add_must_change.py", "add_notifications.py",
    "add_match_alerts.py", "add_messages.py", "add_phone_calls.py",
    "add_item_details.py", "add_post_reports.py", "add_ai_usage.py",
]

tmp = tempfile.mkdtemp(prefix="smartfind_test_")
os.chdir(tmp)   # the app opens "smartfind.db" in the current folder
for script in SETUP:
    done = subprocess.run([sys.executable, os.path.join(HERE, script)],
                          cwd=tmp, capture_output=True, text=True)
    if done.returncode != 0:
        print("SETUP FAILED:", script, done.stderr[-300:])
        os.chdir(HERE)
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(1)

sys.path.insert(0, HERE)
import sqlite3
from werkzeug.security import generate_password_hash
import app as appmod

app = appmod.app
app.config["TESTING"] = True

results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + name)


def db():
    conn = sqlite3.connect("smartfind.db")
    conn.row_factory = sqlite3.Row
    return conn


# --- test users (the admin email is read from admin.txt, if there is one) ---
admin_email = appmod.load_admin_email()
conn = db()
pw = generate_password_hash("Test@12345")
conn.execute("INSERT INTO users (name, email, password_hash, must_change_password) VALUES (?,?,?,0)",
             ("Alice", "alice@test.com", pw))
conn.execute("INSERT INTO users (name, email, password_hash, must_change_password) VALUES (?,?,?,0)",
             ("Bob", "bob@test.com", pw))
if admin_email:
    conn.execute("INSERT INTO users (name, email, password_hash, must_change_password) VALUES (?,?,?,0)",
                 ("Admin", admin_email, pw))
conn.commit()
conn.close()


def login(email):
    c = app.test_client()
    c.post("/login", data={"email": email, "password": "Test@12345"})
    return c


# 1. Logged-out visitors are sent to the login page
anon = app.test_client()
r = anon.get("/")
check("logged-out home redirects to login", r.status_code == 302 and "/login" in r.headers["Location"])
r = anon.get("/item/1")
check("logged-out item page redirects to login", r.status_code == 302 and "/login" in r.headers["Location"])

# 2. Login
r = anon.post("/login", data={"email": "alice@test.com", "password": "wrong"})
check("wrong password rejected", r.status_code == 200 and b"incorrect" in r.data)
alice = app.test_client()
r = alice.post("/login", data={"email": "alice@test.com", "password": "Test@12345"})
check("correct login redirects", r.status_code == 302)

# 3. Main pages open
for path in ["/", "/report", "/my-posts", "/activity", "/notifications", "/profile"]:
    check(f"GET {path} = 200", alice.get(path).status_code == 200)

# 4. Post an item with an extra detail row
r = alice.post("/report", data={
    "status": "lost", "title": "Smoke test bottle", "description": "blue bottle",
    "category": "Bottle", "place": "Library",
    "detail_label": ["Brand"], "detail_value": ["Boat"],
})
check("posting an item redirects", r.status_code == 302)
conn = db()
item = conn.execute("SELECT * FROM items WHERE title = 'Smoke test bottle'").fetchone()
check("item saved in database", item is not None)
item_id = item["id"] if item else 0
n_details = conn.execute("SELECT COUNT(*) FROM item_details WHERE item_id = ?", (item_id,)).fetchone()[0]
conn.close()
check("detail row saved", n_details == 1)

# 5. Item page
r = alice.get(f"/item/{item_id}")
check("item page shows title and detail", r.status_code == 200 and b"Smoke test bottle" in r.data and b"Boat" in r.data)
check("owner does not see Report button", f"/report-post/{item_id}".encode() not in r.data)

# 6. Report this post (another user)
bob = login("bob@test.com")
r = bob.get(f"/item/{item_id}")
check("other user sees Report button", f"/report-post/{item_id}".encode() in r.data)
bob.post(f"/report-post/{item_id}", data={"reason": "spam"})
bob.post(f"/report-post/{item_id}", data={"reason": "fake"})
conn = db()
n_reports = conn.execute("SELECT COUNT(*) FROM post_reports WHERE item_id = ?", (item_id,)).fetchone()[0]
conn.close()
check("report saved once, duplicate ignored", n_reports == 1)
alice.post(f"/report-post/{item_id}", data={"reason": "spam"})
conn = db()
n_reports = conn.execute("SELECT COUNT(*) FROM post_reports WHERE item_id = ?", (item_id,)).fetchone()[0]
conn.close()
check("owner cannot report own post", n_reports == 1)

# 7. Report page assistant (local parser)
r = alice.post("/ai/assist", json={"text": "I lost my black wallet in the Library yesterday"})
data = r.get_json(silent=True) or {}
check("assistant fills a draft", r.status_code == 200 and data.get("draft", {}).get("place") == "Library")
check("assistant needs login", app.test_client().post("/ai/assist", json={"text": "x"}).status_code in (302, 401))

# 8. Admin pages
r = bob.get("/admin/reports")
check("normal user blocked from /admin/reports", r.status_code == 403)
if admin_email:
    adm = login(admin_email)
    check("admin opens /admin/reports", adm.get("/admin/reports").status_code == 200)
    check("admin opens /admin/users", adm.get("/admin/users").status_code == 200)
else:
    print("SKIP  admin checks (no admin.txt)")

# 9. Logout
alice.get("/logout")
r = alice.get("/")
check("after logout, home redirects to login", r.status_code == 302 and "/login" in r.headers["Location"])

os.chdir(HERE)
shutil.rmtree(tmp, ignore_errors=True)
print()
if all(results):
    print(f"ALL {len(results)} CHECKS PASSED")
    sys.exit(0)
print(f"{results.count(False)} OF {len(results)} CHECKS FAILED")
sys.exit(1)
