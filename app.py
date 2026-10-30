import sqlite3
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)


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
    if request.method == "POST":
        conn = get_db()
        conn.execute(
            "INSERT INTO items (title, description, category, location, status, contact_name, contact_email) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                request.form["title"],
                request.form["description"],
                request.form["category"],
                request.form["location"],
                request.form["status"],
                request.form["contact_name"],
                request.form["contact_email"],
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("home"))
    return render_template("report.html")


if __name__ == "__main__":
    app.run(debug=True)