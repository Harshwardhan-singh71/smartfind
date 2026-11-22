import hashlib
import os
import re
import sqlite3
import secrets
import time
import uuid
from datetime import date, datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from matcher import find_matches, why_matched

app = Flask(__name__)
import ai
# Secret key comes from an environment variable. The fallback is only for local testing.
app.secret_key = os.environ.get("SMARTFIND_SECRET_KEY", "dev-only-change-me")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=60)   # stay logged in
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Only send the cookie over HTTPS when deployed (set SMARTFIND_HTTPS=1 there).
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SMARTFIND_HTTPS") == "1"

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


# How long a post stays on the home page and in matching. After this it moves to the
# "Old" tab. The poster can keep it active with one click.
EXPIRE_DAYS = {"lost": 45, "found": 60, "seen": 14}
FRESH_SQL = (
    "date_reported >= CASE status "
    f"WHEN 'seen' THEN datetime('now', '-{EXPIRE_DAYS['seen']} days') "
    f"WHEN 'lost' THEN datetime('now', '-{EXPIRE_DAYS['lost']} days') "
    f"ELSE datetime('now', '-{EXPIRE_DAYS['found']} days') END"
)


def is_old_post(item):
    """True when an unresolved post is past its time limit."""
    if item["resolved"]:
        return False
    try:
        posted = datetime.strptime(item["date_reported"][:19], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return False
    limit = EXPIRE_DAYS.get(item["status"], 60)
    return datetime.utcnow() - posted > timedelta(days=limit)


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
    elif status == "old":
        # Old tab: not returned, but past the time limit
        query += f" AND (resolved = 0 OR resolved IS NULL) AND NOT ({FRESH_SQL})"
    else:
        # All / Lost / Found / Seen: only items that are still active and recent
        query += f" AND (resolved = 0 OR resolved IS NULL) AND {FRESH_SQL}"
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


STRONG_MATCH_PERCENT = 60   # at or above this the matches page calls it a strong match
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
        f"AND (resolved = 0 OR resolved IS NULL) AND {FRESH_SQL} AND user_id != ?",
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
            why = why_matched(lost_item, item)
            why_text = f", {', '.join(why[:2])}" if why else ""
            notify(
                conn, lost_item["user_id"],
                f'Possible match ({percent}%) for your lost "{lost_item["title"]}": '
                f'someone {verb} "{item["title"]}"{why_text}. Is this yours?',
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

        # Extra detail rows (label + value), up to 5, all optional
        labels = request.form.getlist("detail_label")
        values = request.form.getlist("detail_value")
        extra_details = []
        for label, value in zip(labels, values):
            label, value = label.strip()[:40], value.strip()[:200]
            if label and value:
                extra_details.append((label, value))
        extra_details = extra_details[:5]

        title = request.form["title"].strip()
        category = request.form.get("category", "").strip()
        if not category:
            category = "Other"
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO items (title, description, category, location, status, "
            "contact_name, contact_email, user_id, place, place_details, "
            "event_date, event_time, image, private_question, at_security) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                title,
                request.form["description"],
                category,
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
        for label, value in extra_details:
            conn.execute(
                "INSERT INTO item_details (item_id, label, value) VALUES (?, ?, ?)",
                (cur.lastrowid, label, value),
            )
        log_event(conn, cur.lastrowid, "item_posted", session["user_id"],
                  detail=title)
        notify_matches(conn, cur.lastrowid)
        conn.commit()
        conn.close()
        return redirect(url_for("home"))
    return render_template("report.html")


# ---------- AI Feature: Assistant Bot (Report Page Helper) ----------

ASSIST_PLACES = ['Library', 'Mess', 'Canteen', 'Cricket Ground', 'Parking', 'Classroom', 'Lab', 'Hostel', 'Auditorium', 'Sports Complex', 'Lecture Hall', 'Professor Cabin', 'Bus Stop', 'Academic Block']
ASSIST_CATEGORIES = ['Wallet', 'Bottle', 'Electronics', 'Books', 'ID Card', 'Keys', 'Clothing']
ASSIST_DETAIL_LABELS = ['Brand', 'Colour', 'Size', 'Model', 'Sticker / marks', 'Contents']


def local_draft(text):
    """Basic keyword parser. Used when the AI is unavailable, busy, or out of allowance."""
    lower_text = text.lower()
    draft = {
        "status": "lost",
        "title": "",
        "category": "Other",
        "place": "",
        "place_details": "",
        "event_date": "",
        "event_time": "",
        "private_question": "",
        "details": [],
        "description": ""
    }

    # 1. Smart Status Detection
    if any(w in lower_text for w in ["lost", "looking for", "missed", "missing"]):
        draft["status"] = "lost"
    elif any(w in lower_text for w in ["found", "picked up"]):
        draft["status"] = "found"
    elif any(w in lower_text for w in ["seen", "saw", "spotted"]):
        draft["status"] = "seen"

    # 2. Campus Place Detection (with place_details extraction)
    places = ASSIST_PLACES
    for p in places:
        if p.lower() in lower_text:
            draft["place"] = p
            # Extract place details - text after the place name
            idx2 = lower_text.find(p.lower())
            if idx2 != -1:
                after_place = text[idx2 + len(p):].strip()
                # Remove leading prepositions
                after_place = re.sub(r"^(at|in|near|by|around|close to|next to)\s+", "", after_place, flags=re.IGNORECASE)
                # Take first sentence or up to 100 chars
                place_details_match = re.match(r"([^.!?]{1,100})", after_place)
                if place_details_match:
                    draft["place_details"] = place_details_match.group(1).strip().rstrip(".,;")
            break

    # 3. Category Detection
    categories = ASSIST_CATEGORIES
    for cat in categories:
        if cat.lower() in lower_text:
            draft["category"] = cat
            break

    # 4. Date/Time Detection
    # Relative dates
    today = date.today()
    if "today" in lower_text:
        draft["event_date"] = today.strftime("%Y-%m-%d")
    elif "yesterday" in lower_text:
        draft["event_date"] = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    elif "day before yesterday" in lower_text:
        draft["event_date"] = (today - timedelta(days=2)).strftime("%Y-%m-%d")
    # Explicit date patterns (dd/mm, mm/dd, etc.)
    date_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", text)
    if date_match and not draft["event_date"]:
        day, month = int(date_match.group(1)), int(date_match.group(2))
        year = int(date_match.group(3)) if date_match.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            draft["event_date"] = f"{year:04d}-{month:02d}-{day:02d}"
        except ValueError:
            pass

    # Time patterns (e.g., "3pm", "15:30", "this morning", "around 5pm")
    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lower_text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        ampm = time_match.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        draft["event_time"] = f"{hour:02d}:{minute:02d}"
    elif "morning" in lower_text:
        draft["event_time"] = "09:00"
    elif "afternoon" in lower_text:
        draft["event_time"] = "14:00"
    elif "evening" in lower_text:
        draft["event_time"] = "18:00"
    elif "night" in lower_text:
        draft["event_time"] = "21:00"

    # 5. Private question detection (for "found" items)
    if draft["status"] == "found":
        # Look for question-like patterns
        q_match = re.search(r"[?]|\bwhat\b|\bwhich\b|\bwhere\b|\bdescribe\b", lower_text)
        if q_match:
            # Extract the sentence with the question
            sentences = re.split(r"[.!?]", text)
            for s in sentences:
                if "?" in s or re.search(r"\bwhat\b|\bwhich\b|\bwhere\b|\bdescribe\b", s.lower()):
                    draft["private_question"] = s.strip()
                    break

    # 6. High-Performance Title Extraction
    # We strip out "noise" words to find the actual object
    noise = r"\b(i|my|the|a|an|lost|found|seen|saw|spotted|at|in|near|on|today|yesterday|morning|afternoon|evening|looking|for|picked|up)\b"
    # Also strip out the place name if we found it
    clean_title = re.sub(noise, "", lower_text)
    if draft["place"]:
        clean_title = re.sub(rf"\b{draft['place'].lower()}\b", "", clean_title)
    
    # Take the remaining meaningful words
    title_parts = [w.strip() for w in clean_title.split() if len(w) > 1]
    if title_parts:
        draft["title"] = " ".join(title_parts).capitalize()
    else:
        # Fallback to the original text if parsing failed
        draft["title"] = text.capitalize()

    # 7. Extract detail pairs (label/value) from descriptive phrases
    # Common patterns: "black leather wallet", "brand is Nike", "red color", etc.
    detail_labels = ["Brand", "Colour", "Size", "Model", "Sticker / marks", "Contents"]
    found_labels = set()
    
    # Pattern: "label is/value" or "label: value"
    for label in detail_labels:
        label_lower = label.lower().replace("/", "")
        pattern = rf"\b{re.escape(label_lower)}\b\s*(?:is|=|:)\s*([^,.!?]+)"
        match = re.search(pattern, lower_text)
        if match:
            value = match.group(1).strip().rstrip(".,;")
            if value and len(value) > 1:
                draft["details"].append({"label": label, "value": value})
                found_labels.add(label_lower)

    # Pattern: adjective + noun (e.g., "black wallet", "red bottle")
    color_match = re.search(r"\b(black|white|red|blue|green|yellow|pink|purple|orange|brown|grey|gray|silver|gold)\b", lower_text)
    if color_match and "Colour" not in found_labels:
        draft["details"].append({"label": "Colour", "value": color_match.group(1).capitalize()})

    # Limit to 5 details
    draft["details"] = draft["details"][:5]

    # 8. Description (everything they typed is a good start for description)
    draft["description"] = text
    return draft


def _pick(value, allowed):
    """Return the allowed option that matches value (ignoring case), or ''."""
    value = str(value or "").strip().lower()
    for option in allowed:
        if option.lower() == value:
            return option
    return ""


def clean_ai_draft(data, text):
    """Check everything Gemini returned against the form's allowed values."""
    if not isinstance(data, dict):
        return None

    def s(key, limit):
        return str(data.get(key) or "").strip()[:limit]

    status = s("status", 10).lower()
    title = s("title", 100)
    if status not in ("lost", "found", "seen") or not title:
        return None

    today = date.today()
    event_date = ""
    day = parse_day(s("event_date", 10))
    if day and today - timedelta(days=365) <= day <= today:
        event_date = day.isoformat()
    event_time = s("event_time", 5)
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", event_time):
        event_time = ""

    details = []
    raw_details = data.get("details")
    if isinstance(raw_details, list):
        for row in raw_details:
            if not isinstance(row, dict):
                continue
            label = _pick(row.get("label"), ASSIST_DETAIL_LABELS)
            value = str(row.get("value") or "").strip()[:200]
            if label and value:
                details.append({"label": label, "value": value})
    return {
        "status": status,
        "title": title,
        "category": _pick(data.get("category"), ASSIST_CATEGORIES) or "Other",
        "place": _pick(data.get("place"), ASSIST_PLACES),
        "place_details": s("place_details", 100),
        "event_date": event_date,
        "event_time": event_time,
        "private_question": s("private_question", 200) if status == "found" else "",
        "details": details[:5],
        "description": text,   # the student's own words, not text invented by the AI
    }


def ai_draft(text):
    """Ask Gemini (through ai.py) for a form draft. Returns a checked draft or None."""
    today = date.today()
    prompt = (
        "You help fill in a lost-and-found form for a university campus. "
        "Read the student's message and reply with ONLY a JSON object with these keys:\n"
        '- "status": "lost" (they lost it), "found" (they found it and have it) or "seen" (they only saw it somewhere)\n'
        '- "title": short name of the item, at most 8 words\n'
        f'- "category": exactly one of: {", ".join(ASSIST_CATEGORIES)}, Other\n'
        f'- "place": exactly one of: {", ".join(ASSIST_PLACES)}, or "" if none fits\n'
        '- "place_details": short extra location words such as "near the back door", or ""\n'
        f'- "event_date": YYYY-MM-DD (today is {today.isoformat()}, a {today.strftime("%A")}); work out words like yesterday; "" if not stated\n'
        '- "event_time": HH:MM in 24-hour time, or ""\n'
        '- "private_question": only when status is "found": one short question only the real owner could answer, '
        'for example about what is inside or a mark on it. Never include the answer. Otherwise ""\n'
        f'- "details": a list of up to 5 objects {{"label": ..., "value": ...}} where label is one of: {", ".join(ASSIST_DETAIL_LABELS)}\n'
        "Do not invent facts that the message does not state.\n"
        f"Student's message: <<<{text}>>>"
    )
    return clean_ai_draft(ai.ask_json(prompt, fast=True), text)


@app.route("/ai/assist", methods=["POST"])
def ai_assist():
    """Fill the report form from plain words: Gemini first, basic parser as the fallback."""
    if "user_id" not in session:
        return jsonify({"error": "Login required"}), 401

    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text", "")).strip()[:500]
    if not text:
        return jsonify({"error": "No text provided."}), 400

    conn = get_db()
    try:
        # Check in-memory cache first (max 200 entries, drop oldest)
        lower_text = text.lower()
        if lower_text in ai._text_cache:
            # Cache hit: return cached AI result, no AI call, no allowance used
            cached = ai._text_cache[lower_text]
            ai._text_cache.move_to_end(lower_text)
            uses_left = ai.uses_left(conn, session["user_id"])
            return jsonify({"success": True, "draft": cached, "source": "cache", "note": "", "uses_left": uses_left})

        if payload.get("mode") == "basic":
            # instant local draft: no AI, no waiting, no allowance used
            return jsonify({"success": True, "draft": local_draft(text), "source": "basic", "note": "", "uses_left": None})

        draft, source, note = None, "basic", ""
        if not ai.is_available():
            note = "AI is not available right now, so a basic draft was made."
        elif not ai.allow_use(conn, session["user_id"]):
            note = "You have used today's AI quick-fills. Please fill the form by hand."
        else:
            draft = ai_draft(text)
            if draft:
                source = "ai"
            else:
                note = "AI is busy right now, so a basic draft was made."
                ai.refund_use(conn, session["user_id"])
        uses_left = ai.uses_left(conn, session["user_id"])
    except Exception as e:
        print(f"[ai_assist] error: {e}")
        uses_left = 0
    finally:
        conn.close()

    if draft is None:
        draft = local_draft(text)
    else:
        # Store successful AI result in cache for future use
        if source == "ai" and lower_text not in ai._text_cache:
            ai._text_cache[lower_text] = draft
            if len(ai._text_cache) > ai._CACHE_MAX:
                ai._text_cache.popitem(last=False)
    return jsonify({
        "success": True, "draft": draft, "source": source,
        "note": note, "uses_left": uses_left,
    })


@app.route("/ai/photo-assist", methods=["POST"])
def ai_photo_assist():
    """Suggest title, category, and a colour detail from a photo.
    Runs in background; never makes the student wait. Never sends the photo
    if the personal-document checkbox is ticked. Never saves the photo.
    """
    if "user_id" not in session:
        print("[photo-assist] refusal: not logged in")
        return jsonify({"success": False})

    photo = request.files.get("photo")
    is_personal_doc = request.form.get("is_personal_doc") == "1"
    if not photo or not photo.filename:
        print("[photo-assist] refusal: no file")
        return jsonify({"success": False})
    if is_personal_doc:
        print("[photo-assist] refusal: personal doc checkbox ticked")
        return jsonify({"success": False})

    ext = photo.filename.rsplit(".", 1)[-1].lower() if "." in photo.filename else ""
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        print(f"[photo-assist] refusal: bad type ({ext})")
        return jsonify({"success": False})

    photo_bytes = photo.read()
    if len(photo_bytes) > 4 * 1024 * 1024:
        print("[photo-assist] refusal: too big")
        return jsonify({"success": False})

    # mode=basic: instant local colour, no AI call, no allowance used
    if request.form.get("mode") == "basic":
        from photo_bot import local_colour
        colour = local_colour(photo_bytes)
        if colour is None:
            print("[photo-assist] basic mode: local_colour returned None")
            return jsonify({"success": False})
        print(f"[photo-assist] basic mode: colour={colour}")
        return jsonify({
            "success": True,
            "draft": {
                "title": "",
                "category": "Other",
                "details": [{"label": "Colour", "value": colour}],
                "description": "",
            },
        })

    conn = get_db()
    # Check in-memory cache for this image (sha256 of bytes, max 200 entries)
    photo_hash = hashlib.sha256(photo_bytes).hexdigest()
    if photo_hash in ai._photo_cache:
        # Cache hit: return cached draft without AI call or allowance usage
        draft = ai._photo_cache[photo_hash]
        uses_left = ai.uses_left(conn, session["user_id"])
        return jsonify({
            "success": True,
            "draft": {
                "title": draft.get("title", ""),
                "category": draft.get("category", "Other"),
                "details": draft.get("details", []),
                "description": draft.get("description", ""),
            },
            "uses_left": uses_left,
        })

    if not ai.allow_use(conn, session["user_id"]):
        print("[photo-assist] refusal: allowance used up")
        return jsonify({"success": False, "note": "You have used today's photo suggestions. Please fill the form by hand."})

    prompt = (
        "You are helping a student fill a campus lost-and-found form. "
        "Look at the photo and reply with ONLY a JSON object with these keys:\n"
        '- "title": short name of the item, at most 8 words\n'
        f'- "category": exactly one of: {", ".join(ASSIST_CATEGORIES)}, Other\n'
        f'- "details": a list of up to 2 objects with label exactly "Brand" or "Colour" and their values, or [] if not clear\n'
        '- "description": a plain description of the item, at most 120 characters, no markdown\n'
        "Do not invent facts that the photo does not show."
    )
    mime = f"image/{ext}" if ext != "jpg" else "image/jpeg"
    ai_response = ai.ask_image_json(prompt, photo_bytes, mime, fast=True)
    if ai_response is None:
        print(f"[photo-assist] AI returned None: {ai.last_error}")
    else:
        # Debug: print raw AI response
        import json as _json
        print(f"[photo-assist] raw AI response: {_json.dumps(ai_response, ensure_ascii=False)}")
    if ai_response and isinstance(ai_response, dict):
        # clean_ai_draft requires a status; default to "lost" (client can override)
        ai_response.setdefault("status", "lost")
    draft = clean_ai_draft(ai_response, "")
    # For photo assist, use AI's description (max 120 chars, cut at word boundary)
    if draft and isinstance(ai_response, dict):
        raw_desc = str(ai_response.get("description") or "").strip()
        if len(raw_desc) > 120:
            # cut at last space within 120 chars, no trailing space
            ai_desc = raw_desc[:120].rsplit(" ", 1)[0].strip()
        else:
            ai_desc = raw_desc
        if ai_desc:
            draft["description"] = ai_desc
    if draft:
        # Debug: print cleaned draft
        print(f"[photo-assist] cleaned draft: {_json.dumps(draft, ensure_ascii=False)}")
        # Store in cache
        ai._photo_cache[photo_hash] = draft
        if len(ai._photo_cache) > ai._CACHE_MAX:
            ai._photo_cache.popitem(last=False)

    if draft is None:
        ai.refund_use(conn, session["user_id"])
        conn.close()
        return jsonify({"success": False})

    uses_left = ai.uses_left(conn, session["user_id"])
    conn.close()

    # Return only the fields we support; client will fill only empty ones
    return jsonify({
        "success": True,
        "draft": {
            "title": draft.get("title", ""),
            "category": draft.get("category", "Other"),
            "details": draft.get("details", []),
            "description": draft.get("description", ""),
        },
        "uses_left": uses_left,
    })

# ---------- AI/Proactive Feature: Live Match Preview ----------

@app.route("/api/match-preview", methods=["POST"])
def ai_match_preview():
    """Takes unsaved form data and returns top matching items from the database.
    This helps users see if their item is already reported while they are still typing."""
    if "user_id" not in session:
        return jsonify([])

    data = request.json
    target = {
        "status": data.get("status", "lost"),
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "category": data.get("category", "Other"),
        "place": data.get("place", ""),
        "event_date": "" # Date is less critical for a quick preview
    }

    if not target["title"] and not target["description"]:
        return jsonify([])

    conn = get_db()
    # Find items of the opposite status
    wanted = ("found", "seen") if target["status"] == "lost" else ("lost",)
    placeholders = ",".join("?" * len(wanted))
    candidates = conn.execute(
        f"SELECT * FROM items WHERE status IN ({placeholders}) "
        "AND (resolved = 0 OR resolved IS NULL)",
        wanted
    ).fetchall()
    conn.close()

    # Reuse your existing matcher.py logic
    from matcher import find_matches
    results = find_matches(target, candidates, top_n=3)
    
    # Format for JSON
    out = []
    for item, score in results:
        out.append({
            "id": item["id"],
            "title": item["title"],
            "place": item["place"] or item["location"],
            "image": item["image"],
            "score": score,
            "status": item["status"]
        })
    return jsonify(out)@app.route("/register")
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
        session.permanent = True
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
        conn.execute(
            "DELETE FROM call_consent WHERE claim_id IN "
            "(SELECT id FROM claims WHERE item_id = ?)",
            (item_id,),
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
        f"AND (resolved = 0 OR resolved IS NULL) AND {FRESH_SQL}",
        wanted,
    ).fetchall()
    conn.close()

    results = find_matches(item, candidates, top_n=8)
    reasons = {match["id"]: why_matched(item, match) for match, _ in results}
    return render_template(
        "matches.html", item=item, results=results, reasons=reasons,
        strong_from=STRONG_MATCH_PERCENT,
    )


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
    admin = is_admin_user()
    open_reports = 0
    if admin:
        conn = get_db()
        open_reports = conn.execute(
            "SELECT COUNT(DISTINCT item_id) FROM post_reports WHERE status = 'open'"
        ).fetchone()[0]
        conn.close()
    return {"is_admin": admin, "open_reports": open_reports}


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
    conn.execute("DELETE FROM post_reports WHERE item_id = ?", (item_id,))
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


@app.route("/renew/<int:item_id>", methods=["POST"])
def renew_item(item_id):
    conn = get_db()
    item = conn.execute("SELECT user_id, resolved FROM items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        conn.close()
        abort(404)
    if item["user_id"] != session["user_id"] and not is_admin_user():
        conn.close()
        abort(403)
    if not item["resolved"]:
        conn.execute("UPDATE items SET date_reported = CURRENT_TIMESTAMP WHERE id = ?", (item_id,))
        conn.commit()
        flash("Your post is active again.")
    conn.close()
    return redirect(url_for("item_detail", item_id=item_id))


@app.route("/item/<int:item_id>")
def item_detail(item_id):
    conn = get_db()
    item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        conn.close()
        return "Item not found", 404

    details = conn.execute(
        "SELECT label, value FROM item_details WHERE item_id = ? ORDER BY id",
        (item_id,),
    ).fetchall()

    is_owner = "user_id" in session and session["user_id"] == item["user_id"]
    claims = []
    my_claim = None
    has_alert = False
    if item["status"] in ("found", "seen"):
        if is_owner:
            claims = conn.execute(
                "SELECT claims.id, claims.answer, claims.status, claims.created_at, "
                "claims.anonymous, users.name AS claimant_name "
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
        my_claim=my_claim, has_alert=has_alert, details=details,
        is_old=is_old_post(item), expire_days=EXPIRE_DAYS,
    )


PUBLIC_ENDPOINTS = {"login", "register", "static", "ai_photo_assist"}


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


def normalize_phone(raw):
    """Return a clean phone number like +919876543210, or None if it looks wrong."""
    phone = re.sub(r"[\s\-().]", "", raw or "")
    return phone if re.fullmatch(r"\+?\d{7,15}", phone) else None


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
                phone = None
                if len(parts) == 1 and "@" in parts[0]:
                    name, email = parts[0].split("@")[0], parts[0].lower()
                elif len(parts) >= 2 and "@" in parts[1]:
                    name, email = parts[0], parts[1].lower()
                    if len(parts) >= 3 and parts[2]:
                        phone = normalize_phone(parts[2])
                        if phone is None:
                            skipped.append(f"{line}  (phone number looks wrong)")
                            continue
                else:
                    skipped.append(f"{line}  (use: Name, email, phone)")
                    continue
                if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
                    if phone:
                        conn.execute("UPDATE users SET phone = ? WHERE email = ?", (phone, email))
                        skipped.append(f"{email}  (already had an account - phone number updated)")
                    else:
                        skipped.append(f"{email}  (already has an account)")
                    continue
                password = temp_password()
                conn.execute(
                    "INSERT INTO users (name, email, password_hash, must_change_password, phone) "
                    "VALUES (?, ?, ?, 1, ?)",
                    (name, email, generate_password_hash(password), phone),
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


@app.route("/profile", methods=["GET", "POST"])
def profile():
    conn = get_db()
    user = conn.execute(
        "SELECT name, email, phone FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()
    if request.method == "POST":
        raw = request.form.get("phone", "").strip()
        if raw == "":
            conn.execute("UPDATE users SET phone = NULL WHERE id = ?", (session["user_id"],))
            conn.execute("DELETE FROM call_consent WHERE user_id = ?", (session["user_id"],))
            flash("Phone number removed. Calls are switched off in all your chats.")
        else:
            phone = normalize_phone(raw)
            if phone is None:
                conn.close()
                flash("Please enter a valid phone number (7 to 15 digits, optionally starting with +).")
                return redirect(url_for("profile"))
            conn.execute("UPDATE users SET phone = ? WHERE id = ?", (phone, session["user_id"]))
            flash("Phone number saved.")
        conn.commit()
        conn.close()
        return redirect(url_for("profile"))
    conn.close()
    return render_template("profile.html", user=user)


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

    is_sighting = item["status"] == "seen"
    if item["status"] not in ("found", "seen") or item["resolved"]:
        conn.close()
        flash("This item can't be claimed.")
        return redirect(url_for("item_detail", item_id=item_id))

    accepted = None
    if not is_sighting:   # a sighting can have several chats; a found item only one
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

    if item["user_id"] is None:
        conn.close()
        flash("This is a sample item with no owner, so it can't be claimed.")
        return redirect(url_for("item_detail", item_id=item_id))

    existing = conn.execute(
        "SELECT 1 FROM claims WHERE item_id = ? AND claimant_id = ?",
        (item_id, session["user_id"]),
    ).fetchone()
    if existing:
        conn.close()
        flash("You have already sent a request for this item. Please wait for a reply.")
        return redirect(url_for("item_detail", item_id=item_id))

    if request.method == "POST":
        answer = request.form.get("answer", "").strip()
        if not answer:
            conn.close()
            flash("Please write a short message.")
            return redirect(url_for("claim", item_id=item_id))
        anonymous = 1 if request.form.get("anonymous") else 0
        cur = conn.execute(
            "INSERT INTO claims (item_id, claimant_id, answer, anonymous) VALUES (?, ?, ?, ?)",
            (item_id, session["user_id"], answer, anonymous),
        )
        conn.execute(
            "INSERT INTO events (item_id, claim_id, user_id, action) VALUES (?, ?, ?, ?)",
            (item_id, cur.lastrowid, session["user_id"], "claim_created"),
        )
        who = "Someone" if anonymous else session["user_name"]
        if is_sighting:
            note = f'{who} wants to ask about your sighting "{item["title"]}".'
        else:
            note = f'{who} claimed your item "{item["title"]}".'
        notify(conn, item["user_id"], note, url_for("item_detail", item_id=item_id))
        conn.commit()
        conn.close()
        flash("Request sent. You will be notified when they reply." if is_sighting else "Claim sent. The finder will review it.")
        return redirect(url_for("item_detail", item_id=item_id))

    conn.close()
    return render_template("claim.html", item=item, is_sighting=is_sighting)


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
        already = None
        if item["status"] != "seen":
            already = conn.execute(
                "SELECT 1 FROM claims WHERE item_id = ? AND status = 'accepted'",
                (item["id"],),
            ).fetchone()
        if already:
            conn.close()
            flash("You have already accepted a claim for this item.")
            return redirect(link)
        others = []
        if item["status"] != "seen":
            others = conn.execute(
                "SELECT claimant_id FROM claims "
                "WHERE item_id = ? AND id != ? AND status = 'pending'",
                (item["id"], claim_id),
            ).fetchall()
        conn.execute(
            "UPDATE claims SET status = 'accepted', decided_at = CURRENT_TIMESTAMP WHERE id = ?",
            (claim_id,),
        )
        if item["status"] != "seen":
            conn.execute(
                "UPDATE claims SET status = 'rejected', decided_at = CURRENT_TIMESTAMP "
                "WHERE item_id = ? AND id != ? AND status = 'pending'",
                (item["id"], claim_id),
            )
        conn.execute(
            "INSERT INTO events (item_id, claim_id, user_id, action) VALUES (?, ?, ?, ?)",
            (item["id"], claim_id, session["user_id"], "claim_accepted"),
        )
        if item["status"] == "seen":
            accept_note = f'Your request about the sighting "{item["title"]}" was accepted. You can chat now.'
        else:
            accept_note = f'Your claim on "{item["title"]}" was accepted. The finder will arrange the handover.'
        notify(conn, claim["claimant_id"], accept_note, link)
        for o in others:
            notify(
                conn, o["claimant_id"],
                f'Your claim on "{item["title"]}" was not accepted.',
                link,
            )
        flash("Accepted. You can chat now." if item["status"] == "seen" else "Claim accepted. Other pending claims were rejected.")
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
            f'Your request about "{item["title"]}" was not accepted.' if item["status"] == "seen"
            else f'Your claim on "{item["title"]}" was not accepted.',
            link,
        )
        flash("Request declined." if item["status"] == "seen" else "Claim rejected.")

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
    closed = bool(item["resolved"])
    my_allow, their_phone, i_have_phone = get_call_state(conn, claim_id, session["user_id"], closed)
    conn.commit()
    conn.close()
    return render_template(
        "chat.html", claim=claim, item=item, role=role, messages=messages,
        me=session["user_id"], closed=closed,
        my_allow=my_allow, their_phone=their_phone, i_have_phone=i_have_phone,
    )


def get_call_state(conn, claim_id, user_id, closed):
    """Return (my_allow, their_phone, i_have_phone).

    their_phone is only given when the other person has switched on
    "Allow calls" for this chat and the chat is still open."""
    me = conn.execute("SELECT phone FROM users WHERE id = ?", (user_id,)).fetchone()
    i_have_phone = bool(me and me["phone"])
    if closed:
        return False, None, i_have_phone
    my_allow = conn.execute(
        "SELECT 1 FROM call_consent WHERE claim_id = ? AND user_id = ?",
        (claim_id, user_id),
    ).fetchone() is not None
    theirs = conn.execute(
        "SELECT users.phone FROM call_consent JOIN users ON users.id = call_consent.user_id "
        "WHERE call_consent.claim_id = ? AND call_consent.user_id != ?",
        (claim_id, user_id),
    ).fetchone()
    their_phone = theirs["phone"] if theirs and theirs["phone"] else None
    return my_allow, their_phone, i_have_phone


@app.route("/chat/<int:claim_id>/calls", methods=["POST"])
def chat_calls(claim_id):
    conn = get_db()
    claim, item, role = chat_context(conn, claim_id)
    back = url_for("chat", claim_id=claim_id)
    if item["resolved"]:
        conn.close()
        flash("This item was returned, so the chat is now read-only.")
        return redirect(back)

    if request.form.get("action") == "off":
        conn.execute(
            "DELETE FROM call_consent WHERE claim_id = ? AND user_id = ?",
            (claim_id, session["user_id"]),
        )
        flash("Calls are switched off. The other person can no longer see your number.")
    else:
        me = conn.execute("SELECT phone FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        if not me or not me["phone"]:
            conn.close()
            flash("Your account has no phone number yet. Ask the admin to add it.")
            return redirect(back)
        conn.execute(
            "INSERT OR IGNORE INTO call_consent (claim_id, user_id) VALUES (?, ?)",
            (claim_id, session["user_id"]),
        )
        flash("Calls are on. The other person can now call you from this chat.")
    conn.commit()
    conn.close()
    return redirect(back)


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
    claim, item, role = chat_context(conn, claim_id)
    rows = conn.execute(
        "SELECT id, sender_id, body, file_name, created_at FROM messages "
        "WHERE claim_id = ? AND id > ? ORDER BY id",
        (claim_id, after),
    ).fetchall()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND link = ?",
        (session["user_id"], url_for("chat", claim_id=claim_id)),
    )
    _, their_phone, _ = get_call_state(conn, claim_id, session["user_id"], bool(item["resolved"]))
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
    return jsonify({"messages": out, "phone": their_phone})


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
            "claims.created_at, claims.anonymous, items.id AS item_id, items.title, "
            "users.name AS claimant_name "
            "FROM claims JOIN items ON items.id = claims.item_id "
            "JOIN users ON users.id = claims.claimant_id "
            "WHERE items.user_id = ?"
        )
        params = [uid]
        if q:
            query += (" AND (items.title LIKE ? OR (claims.anonymous = 0 AND users.name LIKE ?) "
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
    if user_id is None:
        return
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


REPORT_REASONS = {
    "spam": "Spam or not a real item",
    "fake": "Fake or misleading",
    "abuse": "Rude or abusive",
    "private": "Shows private information",
    "other": "Something else",
}


@app.route("/report-post/<int:item_id>", methods=["POST"])
def report_post(item_id):
    reason = request.form.get("reason", "")
    if reason not in REPORT_REASONS:
        flash("Please choose a reason for the report.")
        return redirect(url_for("item_detail", item_id=item_id))
    note = request.form.get("note", "").strip()[:300] or None

    conn = get_db()
    item = conn.execute(
        "SELECT user_id FROM items WHERE id = ?", (item_id,)
    ).fetchone()
    if item is None:
        conn.close()
        abort(404)
    if item["user_id"] == session["user_id"]:
        conn.close()
        flash("You can't report your own post.")
        return redirect(url_for("item_detail", item_id=item_id))

    cur = conn.execute(
        "INSERT OR IGNORE INTO post_reports (item_id, reporter_id, reason, note) "
        "VALUES (?, ?, ?, ?)",
        (item_id, session["user_id"], reason, note),
    )
    conn.commit()
    conn.close()
    if cur.rowcount:
        flash("Thanks. The admin will review this post.")
    else:
        flash("You have already reported this post.")
    return redirect(url_for("item_detail", item_id=item_id))


@app.route("/admin/reports")
def admin_reports():
    if not is_admin_user():
        abort(403)
    view = request.args.get("view", "open")
    if view not in ("open", "dismissed", "all"):
        view = "open"

    conn = get_db()
    where = "" if view == "all" else "WHERE post_reports.status = ?"
    params = [] if view == "all" else [view]
    rows = conn.execute(
        "SELECT post_reports.id, post_reports.item_id, post_reports.reason, "
        "post_reports.note, post_reports.status, post_reports.created_at, "
        "users.name AS reporter_name, items.title, items.status AS item_status, "
        "items.image, items.user_id AS poster_id, poster.name AS poster_name "
        "FROM post_reports "
        "JOIN items ON items.id = post_reports.item_id "
        "JOIN users ON users.id = post_reports.reporter_id "
        "LEFT JOIN users AS poster ON poster.id = items.user_id "
        f"{where} ORDER BY post_reports.id DESC",
        params,
    ).fetchall()
    conn.close()

    posts = {}
    for r in rows:
        entry = posts.setdefault(r["item_id"], {"item": r, "reports": []})
        entry["reports"].append(r)
    return render_template(
        "admin_reports.html", posts=list(posts.values()), view=view,
        reasons=REPORT_REASONS,
    )


@app.route("/admin/reports/<int:item_id>/dismiss", methods=["POST"])
def admin_reports_dismiss(item_id):
    if not is_admin_user():
        abort(403)
    conn = get_db()
    conn.execute(
        "UPDATE post_reports SET status = 'dismissed' WHERE item_id = ? AND status = 'open'",
        (item_id,),
    )
    conn.commit()
    conn.close()
    flash("Reports dismissed. The post stays up.")
    return redirect(url_for("admin_reports"))


if __name__ == "__main__":
    app.run(debug=True)
