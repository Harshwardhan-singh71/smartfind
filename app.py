import os
import sqlite3
import secrets
import time
import uuid
from datetime import date, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from matcher import find_matches

app = Flask(__name__)
app.secret_key = "change-this-to-any-long-random-text-123"

UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024


def save_image(file):
    """Save an uploaded photo and return its stored file name, or None."""
    if not file or not file.filename:
        return None
    extension = secure_filename(file.filename).rsplit(".", 1)[-1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        return None
    filename = f"{uuid.uuid4().hex}.{extension}"
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return filename


CHAT_UPLOAD_FOLDER = os.path.join(app.root_path, "chat_uploads")   # private, not in /static
CHAT_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}   # shown inside the chat
# Any file type may be shared EXCEPT programs and scripts, which could carry malware.
CHAT_BLOCKED_EXTENSIONS = {
    "exe", "msi", "bat", "cmd", "com", "scr", "pif", "vbs", "vbe", "js", "jse",
    "ps1", "psm1", "sh", "jar", "apk", "dll", "reg", "lnk", "hta", "cpl", "msc",
    "wsf", "wsh", "appx", "dmg", "html", "htm", "xhtml", "svg",
}
CHAT_MAX_BYTES = 10 * 1024 * 1024
os.makedirs(CHAT_UPLOAD_FOLDER, exist_ok=True)


def save_chat_file(file):
    """Save a chat attachment. Returns (stored_name, error_message)."""
    safe = secure_filename(file.filename)
    extension = safe.rsplit(".", 1)[-1].lower() if "." in safe else "bin"
    extension = "".join(ch for ch in extension if ch.isalnum())[:10] or "bin"
    if extension in CHAT_BLOCKED_EXTENSIONS:
        return None, "For safety, programs and scripts (like .exe or .html) can't be shared."
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > CHAT_MAX_BYTES:
        return None, "Files can be at most 10 MB."
    stored = f"{uuid.uuid4().hex}.{extension}"
    file.save(os.path.join(CHAT_UPLOAD_FOLDER, stored))
    return stored, None


@app.errorhandler(413)
def too_large(error):
    flash("That file is too large.")
    return redirect(request.referrer or url_for("report"))


def get_db():
    conn = sqlite3.connect("smartfind.db")
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def home():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")

    query = "SELECT * FROM items WHERE 1=1"
    params = []

    if q:
        query += " AND (title LIKE ? OR description LIKE ? OR location LIKE ? OR category LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like, like]

    if status == "resolved":
        # Resolved tab: only items that were returned
        query += " AND resolved = 1"
    else:
        # All / Lost / Found / Seen: only items that are still active
        query += " AND (resolved = 0 OR resolved IS NULL)"
        if status in ("lost", "found", "seen"):
            query += " AND status = ?"
            params.append(status)

    query += " ORDER BY date_reported DESC"

    conn = get_db()
    items = conn.execute(query, params).fetchall()
    stats = {
        "total": conn.execute("SELECT COUNT(*) FROM items").fetchone()[0],
        "returned": conn.execute("SELECT COUNT(*) FROM items WHERE resolved = 1").fetchone()[0],
        "open": conn.execute(
            "SELECT COUNT(*) FROM items WHERE resolved = 0 OR resolved IS NULL"
        ).fetchone()[0],
    }
    conn.close()
    return render_template("index.html", items=items, q=q, status=status, stats=stats)


def log_event(conn, item_id, action, user_id=None, claim_id=None, detail=None):
    conn.execute(
        "INSERT INTO events (item_id, claim_id, user_id, action, detail) "
        "VALUES (?, ?, ?, ?, ?)",
        (item_id, claim_id, user_id, action, detail),
    )


def parse_day(text):
    try:
        return date.fromisoformat((text or "").strip())
    except ValueError:
        return None


def dates_plausible(lost_item, found_item):
    """A found date earlier than the lost date (with 1 day slack) is impossible."""
    lost_day = parse_day(lost_item["event_date"])
    found_day = parse_day(found_item["event_date"])
    if lost_day and found_day and found_day < lost_day - timedelta(days=1):
        return False
    return True


MATCH_ALERT_MIN = 40   # only alert for matches of at least this percent
MATCH_ALERT_MAX = 3    # at most this many alerts per new post


def notify_matches(conn, item_id):
    """After a new post, alert the people who may want to know about it."""
    item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        return

    wanted = ("found", "seen") if item["status"] == "lost" else ("lost",)
    placeholders = ",".join("?" * len(wanted))
    candidates = conn.execute(
        f"SELECT * FROM items WHERE status IN ({placeholders}) "
        "AND (resolved = 0 OR resolved IS NULL) AND user_id != ?",
        (*wanted, item["user_id"]),
    ).fetchall()

    results = find_matches(item, candidates, top_n=10, min_score=MATCH_ALERT_MIN / 100)

    good = []
    for other, percent in results:
        if item["status"] == "lost":
            lost_item, found_item = item, other
        else:
            lost_item, found_item = other, item

        # Rule 1: same category, unless the text match is very strong
        same_category = (item["category"] or "").strip().lower() == \
                        (other["category"] or "").strip().lower()
        if not (same_category or percent >= 70):
            continue
        # Rule 2: dates must make sense
        if not dates_plausible(lost_item, found_item):
            continue
        # Rule 3: never alert the same pair twice
        already = conn.execute(
            "SELECT 1 FROM match_alerts WHERE lost_item_id = ? AND found_item_id = ?",
            (lost_item["id"], found_item["id"]),
        ).fetchone()
        if already:
            continue

        good.append((other, percent, lost_item, found_item))
        if len(good) == MATCH_ALERT_MAX:
            break

    if not good:
        return

    for other, percent, lost_item, found_item in good:
        conn.execute(
            "INSERT OR IGNORE INTO match_alerts (user_id, lost_item_id, found_item_id) "
            "VALUES (?, ?, ?)",
            (lost_item["user_id"], lost_item["id"], found_item["id"]),
        )

    if item["status"] == "lost":
        count = len(good)
        plural = "es" if count != 1 else ""
        notify(
            conn, item["user_id"],
            f'We found {count} possible match{plural} for your lost "{item["title"]}".',
            url_for("matches", item_id=item["id"]),
        )
    else:
        verb = "found" if item["status"] == "found" else "saw"
        for other, percent, lost_item, found_item in good:
            notify(
                conn, lost_item["user_id"],
                f'Possible match ({percent}%) for your lost "{lost_item["title"]}": '
                f'someone {verb} "{item["title"]}". Is this yours?',
                url_for("item_detail", item_id=item["id"]),
            )


@app.route("/report", methods=["GET", "POST"])
def report():
    if "user_id" not in session:
        flash("Please log in to report an item.")
        return redirect(url_for("login"))
    if request.method == "POST":
        status = request.form["status"]
        if status not in ("lost", "found", "seen"):
            flash("Invalid post type.")
            return redirect(url_for("report"))
        photo = request.files.get("photo")
        image_name = save_image(photo)
        if photo and photo.filename and image_name is None:
            flash("Photo must be a PNG, JPG or WEBP file.")
            return redirect(url_for("report"))
        place = request.form["place"].strip()
        details = request.form.get("place_details", "").strip()
        location = f"{place}, {details}" if details else place

        # Private question and security desk (only for Found items)
        private_question = None
        at_security = 0
        if status == "found":
            private_question = request.form.get("private_question", "").strip() or None
            at_security = 1 if request.form.get("at_security") else 0

        conn = get_db()
        cur = conn.execute(
            "INSERT INTO items (title, description, category, location, status, "
            "contact_name, contact_email, user_id, place, place_details, "
            "event_date, event_time, image, private_question, at_security) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                request.form["title"],
                request.form["description"],
                request.form["category"],
                location,
                status,
                session["user_name"],
                session["user_email"],
                session["user_id"],
                place,
                details,
                request.form.get("event_date", "").strip(),
                request.form.get("event_time", "").strip(),
                image_name,
                private_question,
                at_security,
            ),
        )
        log_event(conn, cur.lastrowid, "item_posted", session["user_id"],
                  detail=request.form["title"])
        notify_matches(conn, cur.lastrowid)
        conn.commit()
        conn.close()
        return redirect(url_for("home"))
    return render_template("report.html")


@app.route("/register")
def register():
    flash("Accounts are created by the admin. Please log in with the email and "
          "temporary password you were sent.")
    return redirect(url_for("login"))


FAILED_LOGINS = {}  # "ip|email" -> [failed count, locked until time]
MAX_ATTEMPTS = 5
LOCK_SECONDS = 600


def is_locked(key):
    entry = FAILED_LOGINS.get(key)
    return bool(entry) and entry[1] > time.time()


def record_failure(key):
    entry = FAILED_LOGINS.setdefault(key, [0, 0])
    entry[0] += 1
    if entry[0] >= MAX_ATTEMPTS:
        entry[1] = time.time() + LOCK_SECONDS
        entry[0] = 0


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        key = f"{request.remote_addr}|{email}"

        if is_locked(key):
            return render_template(
                "no_access.html",
                message="Too many failed attempts. Please wait 10 minutes and try again, "
                        "or contact the admin.",
            ), 429

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            record_failure(key)
            flash("Email or password is incorrect. If you think you should have access, "
                  "contact the admin.")
            return render_template("login.html")

        FAILED_LOGINS.pop(key, None)
        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]
        session["must_change"] = bool(user["must_change_password"])
        if session["must_change"]:
            return redirect(url_for("change_password"))
        return redirect(url_for("home"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/resolve/<int:item_id>", methods=["POST"])
def resolve(item_id):
    conn = get_db()
    if is_admin_user():
        cur = conn.execute(
            "UPDATE items SET resolved = 1 "
            "WHERE id = ? AND (resolved = 0 OR resolved IS NULL)",
            (item_id,),
        )
    else:
        cur = conn.execute(
            "UPDATE items SET resolved = 1 "
            "WHERE id = ? AND user_id = ? AND (resolved = 0 OR resolved IS NULL)",
            (item_id, session["user_id"]),
        )
    if cur.rowcount > 0:
        title = conn.execute(
            "SELECT title FROM items WHERE id = ?", (item_id,)
        ).fetchone()["title"]
        log_event(conn, item_id, "item_resolved", session["user_id"], detail=title)
    conn.commit()
    conn.close()

    if request.args.get("back") == "my":
        return redirect(url_for("my_posts"))
    return redirect(url_for("item_detail", item_id=item_id))


@app.route("/matches/<int:item_id>")
def matches(item_id):
    conn = get_db()
    item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        conn.close()
        return "Item not found", 404

    is_poster = session.get("user_id") is not None and session.get("user_id") == item["user_id"]
    if not (is_poster or is_admin_user()):
        conn.close()
        abort(403)

    # A lost item can match found or seen posts; found and seen posts match lost ones.
    wanted = ("found", "seen") if item["status"] == "lost" else ("lost",)
    placeholders = ",".join("?" * len(wanted))
    candidates = conn.execute(
        f"SELECT * FROM items WHERE status IN ({placeholders}) "
        "AND (resolved = 0 OR resolved IS NULL)",
        wanted,
    ).fetchall()
    conn.close()

    results = find_matches(item, candidates)
    return render_template("matches.html", item=item, results=results)


@app.route("/my-posts")
def my_posts():
    if "user_id" not in session:
        flash("Please log in to see your posts.")
        return redirect(url_for("login"))

    conn = get_db()
    items = conn.execute(
        "SELECT * FROM items WHERE user_id = ? ORDER BY date_reported DESC",
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return render_template("my_posts.html", items=items)


def load_admin_email():
    """Read the admin email from admin.txt (kept out of Git). No file = no admin."""
    try:
        with open(os.path.join(app.root_path, "admin.txt")) as f:
            return f.read().strip().lower()
    except OSError:
        return ""


def is_admin_user():
    admin_email = load_admin_email()
    return bool(admin_email) and session.get("user_email", "").lower() == admin_email


@app.context_processor
def inject_admin():
    return {"is_admin": is_admin_user()}


@app.route("/delete/<int:item_id>", methods=["POST"])
def delete_item(item_id):
    if not is_admin_user():
        flash("Only the admin can delete posts.")
        return redirect(url_for("home"))

    conn = get_db()
    row = conn.execute(
        "SELECT image, title FROM items WHERE id = ?", (item_id,)
    ).fetchone()
    if row:
        log_event(conn, item_id, "item_deleted", session["user_id"], detail=row["title"])
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

    if row and row["image"]:
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, row["image"]))
        except OSError:
            pass

    flash("Post deleted.")
    return redirect(url_for("home"))


@app.route("/item/<int:item_id>")
def item_detail(item_id):
    conn = get_db()
    item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        conn.close()
        return "Item not found", 404

    is_owner = "user_id" in session and session["user_id"] == item["user_id"]
    claims = []
    my_claim = None
    has_alert = False
    if item["status"] == "found":
        if is_owner:
            claims = conn.execute(
                "SELECT claims.id, claims.answer, claims.status, claims.created_at, "
                "users.name AS claimant_name "
                "FROM claims JOIN users ON users.id = claims.claimant_id "
                "WHERE claims.item_id = ? ORDER BY claims.id",
                (item_id,),
            ).fetchall()
        elif "user_id" in session:
            my_claim = conn.execute(
                "SELECT id, status FROM claims WHERE item_id = ? AND claimant_id = ?",
                (item_id, session["user_id"]),
            ).fetchone()
    if "user_id" in session and not is_owner:
        has_alert = conn.execute(
            "SELECT 1 FROM match_alerts "
            "WHERE found_item_id = ? AND user_id = ? AND dismissed = 0",
            (item_id, session["user_id"]),
        ).fetchone() is not None
    conn.close()
    return render_template(
        "item.html", item=item, is_owner=is_owner, claims=claims,
        my_claim=my_claim, has_alert=has_alert,
    )


PUBLIC_ENDPOINTS = {"login", "register", "static"}


@app.before_request
def require_login():
    """Everything except login, register and the stylesheet needs a signed-in user."""
    if request.endpoint is None or request.endpoint in PUBLIC_ENDPOINTS:
        return None
    if "user_id" not in session:
        flash("Please log in with your registered email to continue.")
        return redirect(url_for("login"))
    if session.get("must_change") and request.endpoint not in ("change_password", "logout"):
        return redirect(url_for("change_password"))
    return None


@app.errorhandler(403)
def no_access(error):
    return render_template("no_access.html"), 403


PASSWORD_CHARS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def temp_password():
    return "".join(secrets.choice(PASSWORD_CHARS) for _ in range(8))


@app.route("/admin/users", methods=["GET", "POST"])
def admin_users():
    if not is_admin_user():
        abort(403)

    created = []   # (name, email, temporary password), shown once
    skipped = []

    if request.method == "POST":
        conn = get_db()
        action = request.form.get("action")

        if action == "create":
            for line in request.form.get("people", "").splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) == 1 and "@" in parts[0]:
                    name, email = parts[0].split("@")[0], parts[0].lower()
                elif len(parts) >= 2 and "@" in parts[1]:
                    name, email = parts[0], parts[1].lower()
                else:
                    skipped.append(f"{line}  (use: Name, email)")
                    continue
                if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
                    skipped.append(f"{email}  (already has an account)")
                    continue
                password = temp_password()
                conn.execute(
                    "INSERT INTO users (name, email, password_hash, must_change_password) "
                    "VALUES (?, ?, ?, 1)",
                    (name, email, generate_password_hash(password)),
                )
                created.append((name, email, password))

        elif action == "reset":
            email = request.form.get("email", "").strip().lower()
            user = conn.execute("SELECT name FROM users WHERE email = ?", (email,)).fetchone()
            if user and email != load_admin_email():
                password = temp_password()
                conn.execute(
                    "UPDATE users SET password_hash = ?, must_change_password = 1 WHERE email = ?",
                    (generate_password_hash(password), email),
                )
                created.append((user["name"], email, password))

        conn.commit()
        conn.close()

    conn = get_db()
    users = conn.execute(
        "SELECT name, email, must_change_password FROM users "
        "WHERE lower(email) != ? ORDER BY id DESC",
        (load_admin_email(),),
    ).fetchall()
    conn.close()
    return render_template("admin_users.html", users=users, created=created, skipped=skipped)


@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        current = request.form["current"]
        new = request.form["new"]
        confirm = request.form["confirm"]

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

        error = None
        if not check_password_hash(user["password_hash"], current):
            error = "Your current password is wrong."
        elif len(new) < 8:
            error = "The new password must be at least 8 characters."
        elif new != confirm:
            error = "The two new passwords don't match."
        elif new == current:
            error = "Please choose a password different from the current one."

        if error:
            conn.close()
            flash(error)
            return render_template("change_password.html")

        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
            (generate_password_hash(new), session["user_id"]),
        )
        conn.commit()
        conn.close()
        session["must_change"] = False
        flash("Password updated.")
        return redirect(url_for("home"))
    return render_template("change_password.html")


@app.route("/claim/<int:item_id>", methods=["GET", "POST"])
def claim(item_id):
    conn = get_db()
    item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        conn.close()
        abort(404)

    if item["status"] != "found" or item["resolved"]:
        conn.close()
        flash("This item can't be claimed.")
        return redirect(url_for("item_detail", item_id=item_id))

    accepted = conn.execute(
        "SELECT 1 FROM claims WHERE item_id = ? AND status = 'accepted'", (item_id,)
    ).fetchone()
    if accepted:
        conn.close()
        flash("The finder has already accepted a claim for this item.")
        return redirect(url_for("item_detail", item_id=item_id))

    if item["user_id"] == session["user_id"]:
        conn.close()
        flash("You posted this item, so you can't claim it.")
        return redirect(url_for("item_detail", item_id=item_id))

    existing = conn.execute(
        "SELECT 1 FROM claims WHERE item_id = ? AND claimant_id = ?",
        (item_id, session["user_id"]),
    ).fetchone()
    if existing:
        conn.close()
        flash("You have already claimed this item. Please wait for the finder.")
        return redirect(url_for("item_detail", item_id=item_id))

    if request.method == "POST":
        answer = request.form.get("answer", "").strip()
        if not answer:
            conn.close()
            flash("Please write your answer.")
            return redirect(url_for("claim", item_id=item_id))
        cur = conn.execute(
            "INSERT INTO claims (item_id, claimant_id, answer) VALUES (?, ?, ?)",
            (item_id, session["user_id"], answer),
        )
        conn.execute(
            "INSERT INTO events (item_id, claim_id, user_id, action) VALUES (?, ?, ?, ?)",
            (item_id, cur.lastrowid, session["user_id"], "claim_created"),
        )
        notify(
            conn, item["user_id"],
            f'{session["user_name"]} claimed your item "{item["title"]}".',
            url_for("item_detail", item_id=item_id),
        )
        conn.commit()
        conn.close()
        flash("Claim sent. The finder will review it.")
        return redirect(url_for("item_detail", item_id=item_id))

    conn.close()
    return render_template("claim.html", item=item)


@app.route("/claim/<int:claim_id>/decide", methods=["POST"])
def decide_claim(claim_id):
    action = request.form.get("action")
    if action not in ("accept", "reject"):
        abort(400)

    conn = get_db()
    claim = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if claim is None:
        conn.close()
        abort(404)
    item = conn.execute("SELECT * FROM items WHERE id = ?", (claim["item_id"],)).fetchone()

    # only the person who posted the found item may decide
    if item["user_id"] != session["user_id"]:
        conn.close()
        abort(403)

    if claim["status"] != "pending" or item["resolved"]:
        conn.close()
        flash("This claim has already been decided.")
        return redirect(url_for("item_detail", item_id=item["id"]))

    link = url_for("item_detail", item_id=item["id"])

    if action == "accept":
        already = conn.execute(
            "SELECT 1 FROM claims WHERE item_id = ? AND status = 'accepted'",
            (item["id"],),
        ).fetchone()
        if already:
            conn.close()
            flash("You have already accepted a claim for this item.")
            return redirect(link)
        others = conn.execute(
            "SELECT claimant_id FROM claims "
            "WHERE item_id = ? AND id != ? AND status = 'pending'",
            (item["id"], claim_id),
        ).fetchall()
        conn.execute(
            "UPDATE claims SET status = 'accepted', decided_at = CURRENT_TIMESTAMP WHERE id = ?",
            (claim_id,),
        )
        conn.execute(
            "UPDATE claims SET status = 'rejected', decided_at = CURRENT_TIMESTAMP "
            "WHERE item_id = ? AND id != ? AND status = 'pending'",
            (item["id"], claim_id),
        )
        conn.execute(
            "INSERT INTO events (item_id, claim_id, user_id, action) VALUES (?, ?, ?, ?)",
            (item["id"], claim_id, session["user_id"], "claim_accepted"),
        )
        notify(
            conn, claim["claimant_id"],
            f'Your claim on "{item["title"]}" was accepted. The finder will arrange the handover.',
            link,
        )
        for o in others:
            notify(
                conn, o["claimant_id"],
                f'Your claim on "{item["title"]}" was not accepted.',
                link,
            )
        flash("Claim accepted. Other pending claims were rejected.")
    else:
        conn.execute(
            "UPDATE claims SET status = 'rejected', decided_at = CURRENT_TIMESTAMP WHERE id = ?",
            (claim_id,),
        )
        conn.execute(
            "INSERT INTO events (item_id, claim_id, user_id, action) VALUES (?, ?, ?, ?)",
            (item["id"], claim_id, session["user_id"], "claim_rejected"),
        )
        notify(
            conn, claim["claimant_id"],
            f'Your claim on "{item["title"]}" was not accepted.',
            link,
        )
        flash("Claim rejected.")

    conn.commit()
    conn.close()
    return redirect(link)


@app.route("/match/<int:found_id>/not-mine", methods=["POST"])
def match_not_mine(found_id):
    conn = get_db()
    conn.execute(
        "UPDATE match_alerts SET dismissed = 1 WHERE found_item_id = ? AND user_id = ?",
        (found_id, session["user_id"]),
    )
    conn.commit()
    conn.close()
    flash("Okay, we won't suggest this item for your lost item again.")
    return redirect(url_for("home"))


def chat_context(conn, claim_id):
    """Return (claim, item, role) if the signed-in user may use this chat, else abort."""
    claim = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if claim is None:
        conn.close()
        abort(404)
    item = conn.execute("SELECT * FROM items WHERE id = ?", (claim["item_id"],)).fetchone()
    if item is None or claim["status"] != "accepted":
        conn.close()
        abort(403)
    uid = session["user_id"]
    if uid == item["user_id"]:
        role = "finder"
    elif uid == claim["claimant_id"]:
        role = "claimant"
    else:
        conn.close()
        abort(403)
    return claim, item, role


@app.route("/chat/<int:claim_id>")
def chat(claim_id):
    conn = get_db()
    claim, item, role = chat_context(conn, claim_id)
    messages = conn.execute(
        "SELECT * FROM messages WHERE claim_id = ? ORDER BY id", (claim_id,)
    ).fetchall()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND link = ?",
        (session["user_id"], url_for("chat", claim_id=claim_id)),
    )
    conn.commit()
    conn.close()
    return render_template(
        "chat.html", claim=claim, item=item, role=role, messages=messages,
        me=session["user_id"], closed=bool(item["resolved"]),
    )


@app.route("/chat/<int:claim_id>/send", methods=["POST"])
def chat_send(claim_id):
    conn = get_db()
    claim, item, role = chat_context(conn, claim_id)
    back = url_for("chat", claim_id=claim_id)
    if item["resolved"]:
        conn.close()
        flash("This item was returned, so the chat is now read-only.")
        return redirect(back)

    body = request.form.get("body", "").strip()
    upload = request.files.get("file")
    has_file = bool(upload and upload.filename)

    if not body and not has_file:
        conn.close()
        flash("Please type a message or attach a file.")
        return redirect(back)
    if len(body) > 1000:
        conn.close()
        flash("Messages can be at most 1000 characters.")
        return redirect(back)

    stored_name = None
    if has_file:
        stored_name, error = save_chat_file(upload)
        if error:
            conn.close()
            flash(error)
            return redirect(back)

    conn.execute(
        "INSERT INTO messages (claim_id, sender_id, body, file_name) VALUES (?, ?, ?, ?)",
        (claim_id, session["user_id"], body or None, stored_name),
    )
    other_id = claim["claimant_id"] if role == "finder" else item["user_id"]
    unread = conn.execute(
        "SELECT 1 FROM notifications WHERE user_id = ? AND link = ? AND is_read = 0",
        (other_id, back),
    ).fetchone()
    if not unread:
        notify(conn, other_id, f'New message about "{item["title"]}".', back)
    conn.commit()
    conn.close()
    return redirect(back)


@app.route("/chat/<int:claim_id>/file/<name>")
def chat_file(claim_id, name):
    """Serve a chat attachment, only to the two people in this chat."""
    conn = get_db()
    chat_context(conn, claim_id)
    row = conn.execute(
        "SELECT 1 FROM messages WHERE claim_id = ? AND file_name = ?", (claim_id, name)
    ).fetchone()
    conn.close()
    if row is None:
        abort(404)
    extension = name.rsplit(".", 1)[-1].lower()
    response = send_from_directory(
        CHAT_UPLOAD_FOLDER, name, as_attachment=(extension not in CHAT_IMAGE_EXTENSIONS)
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response


@app.route("/chat/<int:claim_id>/new")
def chat_new(claim_id):
    after = request.args.get("after", 0, type=int)
    conn = get_db()
    chat_context(conn, claim_id)
    rows = conn.execute(
        "SELECT id, sender_id, body, file_name, created_at FROM messages "
        "WHERE claim_id = ? AND id > ? ORDER BY id",
        (claim_id, after),
    ).fetchall()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND link = ?",
        (session["user_id"], url_for("chat", claim_id=claim_id)),
    )
    conn.commit()
    conn.close()
    out = []
    for r in rows:
        file_url = None
        is_image = False
        ext = ""
        if r["file_name"]:
            file_url = url_for("chat_file", claim_id=claim_id, name=r["file_name"])
            ext = r["file_name"].rsplit(".", 1)[-1].lower()
            is_image = ext in CHAT_IMAGE_EXTENSIONS
        out.append({
            "id": r["id"], "mine": r["sender_id"] == session["user_id"],
            "body": r["body"] or "", "time": r["created_at"],
            "file_url": file_url, "is_image": is_image, "ext": ext,
        })
    return jsonify(out)


@app.route("/activity")
def activity():
    uid = session["user_id"]
    view = request.args.get("view", "posts")
    if view not in ("posts", "sent", "received"):
        view = "posts"
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    like = f"%{q}%"

    if view == "posts":
        filters = [("", "All"), ("lost", "Lost"), ("found", "Found"),
                   ("seen", "Seen"), ("resolved", "Resolved")]
    else:
        filters = [("", "All"), ("pending", "Pending"),
                   ("accepted", "Accepted"), ("rejected", "Rejected")]
    if status not in [f[0] for f in filters]:
        status = ""

    conn = get_db()

    if view == "posts":
        query = (
            "SELECT items.*, "
            "(SELECT COUNT(*) FROM claims WHERE claims.item_id = items.id "
            "AND claims.status = 'pending') AS pending_claims "
            "FROM items WHERE items.user_id = ?"
        )
        params = [uid]
        if q:
            query += (" AND (items.title LIKE ? OR items.description LIKE ? "
                      "OR items.location LIKE ? OR items.category LIKE ?)")
            params += [like, like, like, like]
        if status == "resolved":
            query += " AND items.resolved = 1"
        elif status:
            query += " AND items.status = ?"
            params.append(status)
        query += " ORDER BY items.date_reported DESC"
    elif view == "sent":
        query = (
            "SELECT claims.id, claims.status AS claim_status, claims.answer, "
            "claims.created_at, items.id AS item_id, items.title, items.location "
            "FROM claims JOIN items ON items.id = claims.item_id "
            "WHERE claims.claimant_id = ?"
        )
        params = [uid]
        if q:
            query += (" AND (items.title LIKE ? OR items.location LIKE ? "
                      "OR claims.answer LIKE ?)")
            params += [like, like, like]
        if status:
            query += " AND claims.status = ?"
            params.append(status)
        query += " ORDER BY claims.id DESC"
    else:
        query = (
            "SELECT claims.id, claims.status AS claim_status, claims.answer, "
            "claims.created_at, items.id AS item_id, items.title, "
            "users.name AS claimant_name "
            "FROM claims JOIN items ON items.id = claims.item_id "
            "JOIN users ON users.id = claims.claimant_id "
            "WHERE items.user_id = ?"
        )
        params = [uid]
        if q:
            query += (" AND (items.title LIKE ? OR users.name LIKE ? "
                      "OR claims.answer LIKE ?)")
            params += [like, like, like]
        if status:
            query += " AND claims.status = ?"
            params.append(status)
        query += " ORDER BY claims.id DESC"

    rows = conn.execute(query, params).fetchall()
    pending_received = conn.execute(
        "SELECT COUNT(*) FROM claims JOIN items ON items.id = claims.item_id "
        "WHERE items.user_id = ? AND claims.status = 'pending'",
        (uid,),
    ).fetchone()[0]
    conn.close()

    return render_template(
        "activity.html", rows=rows, view=view, q=q, status=status,
        filters=filters, pending_received=pending_received,
    )


@app.route("/admin/activity")
def admin_activity():
    if not is_admin_user():
        abort(403)

    allowed = ("item_posted", "claim_created", "claim_accepted",
               "claim_rejected", "item_resolved", "item_deleted")
    q = request.args.get("q", "").strip()
    action = request.args.get("action", "")
    if action not in allowed:
        action = ""
    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1
    per_page = 24
    like = f"%{q}%"

    query = (
        "SELECT events.id, events.action, events.created_at, events.item_id, "
        "COALESCE(items.title, events.detail) AS item_title, "
        "items.status AS item_status, "
        "actor.name AS actor_name, claimant.name AS claimant_name, "
        "claims.answer AS answer "
        "FROM events "
        "LEFT JOIN items ON items.id = events.item_id "
        "LEFT JOIN users AS actor ON actor.id = events.user_id "
        "LEFT JOIN claims ON claims.id = events.claim_id "
        "LEFT JOIN users AS claimant ON claimant.id = claims.claimant_id "
        "WHERE 1=1"
    )
    params = []
    if q:
        query += (" AND (COALESCE(items.title, events.detail) LIKE ? "
                  "OR actor.name LIKE ? OR claimant.name LIKE ?)")
        params += [like, like, like]
    if action:
        query += " AND events.action = ?"
        params.append(action)
    query += " ORDER BY events.id DESC LIMIT ? OFFSET ?"
    params += [per_page + 1, (page - 1) * per_page]

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    has_next = len(rows) > per_page
    rows = rows[:per_page]
    return render_template(
        "admin_activity.html", rows=rows, q=q, action=action,
        page=page, has_next=has_next,
    )


def notify(conn, user_id, message, link=None):
    conn.execute(
        "INSERT INTO notifications (user_id, message, link) VALUES (?, ?, ?)",
        (user_id, message, link),
    )


@app.context_processor
def inject_notifications():
    count = 0
    recent = []
    if "user_id" in session:
        conn = get_db()
        count = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
            (session["user_id"],),
        ).fetchone()[0]
        recent = conn.execute(
            "SELECT id, message, link, is_read, created_at FROM notifications "
            "WHERE user_id = ? ORDER BY id DESC LIMIT 5",
            (session["user_id"],),
        ).fetchall()
        conn.close()
    return {"unread_count": count, "recent_notifications": recent}


@app.route("/notifications")
def notifications():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 100",
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return render_template("notifications.html", rows=rows)


@app.route("/notifications/<int:nid>/go")
def notification_go(nid):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM notifications WHERE id = ? AND user_id = ?",
        (nid, session["user_id"]),
    ).fetchone()
    if row is None:
        conn.close()
        abort(404)
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (nid,))
    conn.commit()
    conn.close()
    return redirect(row["link"] or url_for("notifications"))


@app.route("/notifications/read-all", methods=["POST"])
def notifications_read_all():
    conn = get_db()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ?",
        (session["user_id"],),
    )
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for("notifications"))


if __name__ == "__main__":
    app.run(debug=True)
