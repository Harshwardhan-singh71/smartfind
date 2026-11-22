"""SmartFind's one safe door to Gemini.

Every AI feature calls this file. It makes sure that:
  * the site keeps working if the key is missing, the AI is slow, or the daily limit is hit
    (every function returns None instead of raising an error),
  * each user has a small daily allowance, so nobody can use up everyone's free quota,
  * phone numbers, ID numbers, card numbers and emails are removed from the text before it
    is sent (the free tier may use prompts to improve Google's products).
"""
import json
import os
import re
import sqlite3
import time
from collections import OrderedDict

MODEL = "gemini-3.8-flash"     # the model name in Google's current docs; override with GEMINI_MODEL
DAILY_LIMIT = 10                # AI actions per user per day
GLOBAL_DAILY_LIMIT = 450        # site-wide daily budget; override with GEMINI_GLOBAL_LIMIT env var
TIMEOUT_MS = 10000              # give up on a slow answer after 10 seconds (nobody should wait longer)
IMAGE_TIMEOUT_MS = 15000        # give up on a slow image answer after 15 seconds
RETRY_WAIT = 2                  # seconds to wait before one retry when Gemini is busy (503/504)
BREAKER_PAUSE = 30              # after 2 consecutive busy/timeout errors, pause AI for this long
PAUSE_SECONDS = 60              # after a quota error, stop calling the AI for this long

_client = None
_paused_until = 0.0
last_error = None   # the most recent problem, for debugging (never shown to users)

# Circuit breaker state for consecutive busy/timeout failures
_consecutive_failures = 0   # counts consecutive busy/timeout errors
_cb_until = 0.0               # until when the circuit breaker pause is active

# In-memory caches: sha256(image_bytes) -> cleaned draft, max 200 entries
_photo_cache = OrderedDict()  # for ai_photo_assist
_text_cache = OrderedDict()   # for ai_assist, keyed by lowercased text
_CACHE_MAX = 200


def load_env(path=".env"):
    """Read KEY=value lines from .env (no extra package needed)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()


def is_available():
    """True when a key is set and the AI is not paused after a quota error or circuit breaker."""
    return (
        bool(os.environ.get("GEMINI_API_KEY"))
        and time.time() >= _paused_until
        and time.time() >= _cb_until
    )


def _cache_get_or_set(cache, key, factory, max_entries):
    """Return cached value if present, otherwise compute via factory, cache it, and trim."""
    if key in cache:
        cache.move_to_end(key)
        return cache[key]
    value = factory()
    cache[key] = value
    if len(cache) > max_entries:
        cache.popitem(last=False)
    return value

# ---------- privacy: remove sensitive details before anything is sent ----------

_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email removed]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[card number removed]"),
    (re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b"), "[ID number removed]"),
    (re.compile(r"(?<!\d)(?:\+?91[ -]?)?[6-9]\d{4}[ -]?\d{5}(?!\d)"), "[phone removed]"),
    (re.compile(r"(?<!\d)\+?\d[\d -]{8,}\d(?!\d)"), "[number removed]"),
]


def redact(text):
    """Return the text with emails, phone numbers and long ID/card numbers blanked out."""
    text = text or ""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ---------- per-user daily allowance ----------

def allow_use(conn, user_id, limit=DAILY_LIMIT):
    """Count one AI action for this user today. Returns False when the allowance is used up.
    Checks both user and global (user_id=0) usage; returns False if either is at limit."""
    conn.execute(
        "INSERT OR IGNORE INTO ai_usage (user_id, day, used) VALUES (?, date('now'), 0)", (user_id,)
    )
    conn.execute(
        "INSERT OR IGNORE INTO ai_usage (user_id, day, used) VALUES (?, date('now'), 0)", (0,)
    )
    user_used = conn.execute(
        "SELECT used FROM ai_usage WHERE user_id = ? AND day = date('now')", (user_id,)
    ).fetchone()[0]
    global_used = conn.execute(
        "SELECT used FROM ai_usage WHERE user_id = 0 AND day = date('now')"
    ).fetchone()[0]
    if user_used >= limit or global_used >= GLOBAL_DAILY_LIMIT:
        return False
    conn.execute(
        "UPDATE ai_usage SET used = used + 1 WHERE user_id = ? AND day = date('now')", (user_id,)
    )
    conn.execute(
        "UPDATE ai_usage SET used = used + 1 WHERE user_id = 0 AND day = date('now')"
    )
    conn.commit()
    return True


def uses_left(conn, user_id, limit=DAILY_LIMIT):
    row = conn.execute(
        "SELECT used FROM ai_usage WHERE user_id = ? AND day = date('now')", (user_id,)
    ).fetchone()
    return limit - (row[0] if row else 0)


def refund_use(conn, user_id):
    """Refund one AI action for this user and the global budget.
    Both the user row and the global row (user_id=0) are decremented if > 0."""
    conn.execute(
        "UPDATE ai_usage SET used = used - 1 WHERE user_id = ? AND day = date('now') AND used > 0",
        (user_id,),
    )
    conn.execute(
        "UPDATE ai_usage SET used = used - 1 WHERE user_id = 0 AND day = date('now') AND used > 0"
    )
    conn.commit()


# ---------- talking to Gemini ----------

def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def ask_text(prompt, json_mode=False, fast=False):
    """Send a prompt, return the reply text, or None if anything goes wrong.
    fast=True: no retries; if Gemini is busy, the circuit breaker may pause AI."""
    global _paused_until, last_error, _consecutive_failures, _cb_until
    last_error = None
    if not is_available():
        last_error = "AI unavailable (no key, or paused after a quota error)"
        return None
    config = None
    if json_mode:
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0.2,
                http_options=types.HttpOptions(timeout=TIMEOUT_MS),
            )
        except Exception as error:
            last_error = f"{type(error).__name__}: {str(error)[:300]}"
            return None

    for attempt in (1, 2):
        try:
            reply = _get_client().models.generate_content(
                model=os.environ.get("GEMINI_MODEL", MODEL),
                contents=redact(prompt),
                config=config,
            )
            text = (reply.text or "").strip()
            if not text:
                last_error = "Gemini returned an empty answer"
                _consecutive_failures = 0
            else:
                _consecutive_failures = 0
            return text or None
        except Exception as error:   # slow, offline, bad key, quota... never crash the site
            last_error = f"{type(error).__name__}: {str(error)[:300]}"
            message = str(error).lower()
            if ("429" in message or "quota" in message or "exhausted" in message) and attempt == 1 and not fast:
                time.sleep(5)
                continue
            if "429" in message or "quota" in message or "exhausted" in message:
                _paused_until = time.time() + PAUSE_SECONDS
                _consecutive_failures = 0
                return None
            busy = ("503" in message or "504" in message or "unavailable" in message
                    or "deadline" in message or "timed out" in message or "timeout" in message)
            
            if busy:
                _consecutive_failures += 1
                if _consecutive_failures >= 2:
                    _cb_until = time.time() + BREAKER_PAUSE
                    _consecutive_failures = 0
                    return None
                if attempt == 1:
                    time.sleep(RETRY_WAIT)
                    continue
            else:
                _consecutive_failures = 0
            return None
    return None
def ask_json(prompt, fast=False):
    """Like ask_text, but returns a Python dict/list parsed from the reply, or None."""
    text = ask_text(prompt, json_mode=True, fast=fast)
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except ValueError:
        return None


def _call_gemini_image(prompt, image_bytes, mime_type, json_mode=False, fast=False):
    """Internal: send prompt + image to Gemini. Returns reply text or None."""
    global _paused_until, last_error, _consecutive_failures, _cb_until
    last_error = None
    if not is_available():
        last_error = "AI unavailable (no key, or paused after a quota error)"
        return None
    config = None
    if json_mode:
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0.2,
                http_options=types.HttpOptions(timeout=IMAGE_TIMEOUT_MS),
            )
        except Exception as error:
            last_error = f"{type(error).__name__}: {str(error)[:300]}"
            return None

    for attempt in (1, 2):
        try:
            from google.genai import types
            image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            reply = _get_client().models.generate_content(
                model=os.environ.get("GEMINI_MODEL", MODEL),
                contents=[prompt, image_part],
                config=config,
            )
            text = (reply.text or "").strip()
            if not text:
                last_error = "Gemini returned an empty answer"
                _consecutive_failures = 0
            else:
                _consecutive_failures = 0
            return text or None
        except Exception as error:
            last_error = f"{type(error).__name__}: {str(error)[:300]}"
            message = str(error).lower()
            if ("429" in message or "quota" in message or "exhausted" in message) and attempt == 1 and not fast:
                time.sleep(5)
                continue
            if "429" in message or "quota" in message or "exhausted" in message:
                _paused_until = time.time() + PAUSE_SECONDS
                _consecutive_failures = 0
                return None
            busy = ("503" in message or "504" in message or "unavailable" in message
                    or "deadline" in message or "timed out" in message or "timeout" in message)
            
            if busy:
                _consecutive_failures += 1
                if _consecutive_failures >= 2:
                    _cb_until = time.time() + BREAKER_PAUSE
                    _consecutive_failures = 0
                    return None
                if attempt == 1:
                    time.sleep(RETRY_WAIT)
                    continue
            else:
                _consecutive_failures = 0
            return None
    return None
def ask_image(prompt, image_bytes, mime_type, fast=False):
    """Send a prompt with an image, return the reply text, or None if anything goes wrong.
    fast=True: no retries; if Gemini is busy, the circuit breaker may pause AI."""
    result = _call_gemini_image(prompt, image_bytes, mime_type, json_mode=False, fast=fast)
    if result is None:
        print(f"[ai.ask_image] returned None: {last_error}")
    return result


def ask_image_json(prompt, image_bytes, mime_type, fast=False):
    """Like ask_image, but returns a Python dict/list parsed from the reply, or None."""
    text = _call_gemini_image(prompt, image_bytes, mime_type, json_mode=True, fast=fast)
    if not text:
        print(f"[ai.ask_image_json] _call_gemini_image returned None: {last_error}")
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except ValueError as e:
        print(f"[ai.ask_image_json] JSON parse failed: {e}")
        return None
