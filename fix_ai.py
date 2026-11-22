with open(r'c:\projects\smartfind_v3\ai.py', 'r') as f:
    content = f.read()

old = """def ask_text(prompt, json_mode=False, fast=False):
    """Send a prompt, return the reply text, or None if anything goes wrong.
    fast=True: no retries; if Gemini is busy, pause AI for BUSY_PAUSE seconds so the next
    users skip it instantly instead of waiting."""
    global _paused_until, last_error
    last_error = None
    if not is_available():
        last_error = "AI unavailable (no key, or paused after a quota error)"
        return None
    config = None
    if json_mode:
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0.2
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
            return text or None
        except Exception as error:   # slow, offline, bad key, quota... never crash the site
            last_error = f"{type(error).__name__}: {str(error)[:300]}"
            message = str(error).lower()
            if (("429" in message or "quota" in message or "exhausted" in message) and attempt == 1 and not fast):
                time.sleep(5)
                continue
            if "429" in message or "quota" in message or "exhausted" in message:
                _paused_until = time.time() + PAUSE_SECONDS
                return None
            busy = "503" in message or "504" in message or "unavailable" in message or "deadline" in message or "timed out" in message or "timeout" in message
            if busy and fast:
                _paused_until = time.time() + BUSY_PAUSE
                return None
            if busy and attempt == 1:
                time.sleep(RETRY_WAIT)
                continue
            return None
    return None"""

new = """def ask_text(prompt, json_mode=False, fast=False):
    """Send a prompt, return the reply text, or None if anything goes wrong.
    fast=True: no retries; if Gemini is busy, the circuit breaker may pause AI."""
    global _paused_until, last_error, _consecutive_failures
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
    return None"""

if old in content:
    content = content.replace(old, new)
    with open(r'c:\projects\smartfind_v3\ai.py', 'w') as f:
        f.write(content)
    print('Replaced ask_text successfully')
else:
    print('ask_text old text NOT found')
    # Let's check what's there
    if 'def ask_text' in content:
        print('ask_text function exists')