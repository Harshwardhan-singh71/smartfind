import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-to-any-long-random-text-123"


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
    if status in ("lost", "found"):
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY date_reported DESC"

    conn = get_db()
    items = conn.execute(query, params).fetchall()
    conn.close()
    return render_template("index.html", items=items, q=q, status=status)


@app.route("/report", methods=["GET", "POST"])
def report():
    if "user_id" not in session:
        flash("Please log in to report an item.")
        return redirect(url_for("login"))

    if request.method == "POST":
        conn = get_db()
        conn.execute(
            "INSERT INTO items (title, description, category, location, status, contact_name, contact_email, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                request.form["title"],
                request.form["description"],
                request.form["category"],
                request.form["location"],
                request.form["status"],
                session["user_name"],
                session["user_email"],
                session["user_id"],
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("home"))
    return render_template("report.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if len(password) < 6:
            flash("Password must be at least 6 characters.")
            return render_template("register.html")

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("That email is already registered.")
            return render_template("register.html")
        conn.close()
        return redirect(url_for("home"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            return redirect(url_for("home"))

        flash("Wrong email or password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/resolve/<int:item_id>", methods=["POST"])
def resolve(item_id):
    if "user_id" not in session:
        flash("Please log in first.")
        return redirect(url_for("login"))

    conn = get_db()
    conn.execute(
        "UPDATE items SET resolved = 1 WHERE id = ? AND user_id = ?",
        (item_id, session["user_id"]),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)