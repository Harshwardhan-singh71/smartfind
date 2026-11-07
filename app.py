import os
import sqlite3
import secrets
import time
import uuid

from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
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


@app.errorhandler(413)
def too_large(error):
    flash("Photo is too large. Maximum size is 20 MB.")
    return redirect(url_for("report"))

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
        conn.execute(
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
        conn.execute("UPDATE items SET resolved = 1 WHERE id = ?", (item_id,))
    else:
        conn.execute(
            "UPDATE items SET resolved = 1 WHERE id = ? AND user_id = ?",
            (item_id, session["user_id"]),
        )
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
    row = conn.execute("SELECT image FROM items WHERE id = ?", (item_id,)).fetchone()
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
    conn.close()
    if item is None:
        return "Item not found", 404

    is_owner = "user_id" in session and session["user_id"] == item["user_id"]
    return render_template("item.html", item=item, is_owner=is_owner)
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
if __name__ == "__main__":
    app.run(debug=True)