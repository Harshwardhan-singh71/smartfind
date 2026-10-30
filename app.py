import sqlite3
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)


def get_db():
    conn = sqlite3.connect("smartfind.db")
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def home():
    conn = get_db()
    items = conn.execute(
        "SELECT * FROM items ORDER BY date_reported DESC"
    ).fetchall()
    conn.close()
    return render_template("index.html", items=items)


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