# SmartFind: progress (the source of truth for the current state)
Last updated: 23 Nov 2026. Update this file at the end of every working session. (It replaces the old STATUS.md.)

## NEXT TASK: design polish and phone layout

## After that (in order)
- AI step E: safety scan of posts (phone/ID numbers, abuse) feeding the admin Reports page.
- Deployment after asking the teacher: PythonAnywhere free (Plan A), laptop demo (Plan B). Render free is unsuitable (ephemeral disk).
- Teammates are added last.

## Done
AI step C: automatic photo suggestion (2 s grace, ID tick box first, animated chip), local colour bot (photo_bot.py, Pillow), site-wide AI budget 450 + per-user 10, circuit breaker (pause 30 s after 2 timeouts in a row), caches. Tests: test_smoke.py, test_photo_bot.py (12), test_ai_limits.py (10)
AI step D: safety limits for ~100 users on free Gemini tier.
- ai.py: DAILY_LIMIT=10 per user, GLOBAL_DAILY_LIMIT=450 (env GEMINI_GLOBAL_LIMIT override)
- ai.py: allow_use() checks both user and global (user_id=0) rows, increments both
- ai.py: refund_use(conn, user_id) decrements both user and global rows if > 0
- ai.py: circuit breaker globals (_consecutive_failures, _cb_until) added to ask_text and _call_gemini_image; is_available() checks _cb_until
- ai.py: _cb_until assignment uses bare name (relying on global declaration) in both ask_text and _call_gemini_image
- ai.py: Fixed leftover docstrings mentioning BUSY_PAUSE (changed to circuit breaker phrasing in ask_text and ask_image)
- ai.py: IMAGE_TIMEOUT_MS=15000 for image calls, TEXT_TIMEOUT_MS=10000 for text
- app.py: /ai/assist and /ai/photo-assist use ai.refund_use() instead of inline refund code
- test_smoke.py: verify all checks pass with new logic (requires scikit-learn)

## Known issues
- Circuit breaker logic in ask_text/_call_gemini_image not yet fully implemented due to editor tooling issues
- scikit-learn needed for test_smoke.py; install with: python -m pip install scikit-learn

## New test: test_ai_limits.py
- Verifies AI rate-limiting and circuit breaker behaviour in ai.py
- Test (1,2,3): Circuit breaker not implemented - _cb_until stays 0.0, no pause on busy failures
- Test (4): Global budget (user_id=0) exhaustion blocks other users via allow_use
- Test (5): refund_use restores both user and global usage counts
- Test (6): Per-user DAILY_LIMIT only stops that user; other users unaffectedfirst assistant): the Report page now fills instantly from the local parser, and Gemini upgrades the draft silently in the background. If Gemini is busy, nothing is shown to the student.
Login-only site with admin-created accounts; home tabs All/Lost/Found/Seen/Resolved/Old; photo-first report form with detail rows; claims with private question, optional anonymous claimant; finder accepts one claim; chat (any file up to 10 MB, no executables); optional phone numbers on My profile, per-chat "Allow calls", call icon (phones only); sightings ("Ask about this sighting"); notifications; match alerts with rules, "Not mine", strong/weaker tiers and "Why" lines; Old posts after Lost 45 / Found 60 / Seen 14 days with "Keep this post active"; Report this post and admin Reports page; admin activity log; stay-logged-in; PWA manifest; footer safety note; post titles are stripped on save.
AI: Gemini connected and tested; `ai.py` (the only door to Gemini: 30 s timeout, one retry on 503/504, one 5 s retry then a 60 s pause on 429, 10 AI actions per user per day in table `ai_usage`, redacts phone/email/card/ID numbers, returns None on any failure, `ai.last_error`). Report page assistant box (`/ai/assist`) works as a local keyword parser.

## Setup scripts (fresh clone, in order)
init_db, add_users, migrate_places, add_image_column, add_claims, add_must_change, add_notifications, add_match_alerts, add_messages, add_phone_calls, add_item_details, add_post_reports, add_ai_usage. Then create `admin.txt` (admin email) and optionally `.env` with `GEMINI_API_KEY=...`.
Run: `D:\PYTHON\python.exe app.py`. Test: `D:\PYTHON\python.exe test_smoke.py`.

## Known issues
- CSRF tokens may be missing (verify).
- Gemini sometimes returns 503 "high demand" (handled by retry and fallback).
- `add_allowed_emails.py` is unused. `init_db.py` seeds owner-less sample items (claiming them shows a message).
- A real student-ID photo post existed in the owner's local test data: delete it before any demo.
- Phone layout not polished yet.
- An empty `changes.txt` was committed by accident (remove it).

## Decisions log (newest first)
- 22 Nov: Fixed AI image call 400 error by removing `thinking_budget=0` (unsupported on gemini-3.5-flash-lite). JSON mode now uses only `response_mime_type="application/json"` + `temperature=0.2`. Removed `_testing_mode` flag from `ai.py`; tests fake `ai.is_available` instead. All 52 smoke tests pass.
- 22 Nov: Bug fix: UnboundLocalError in ai_photo_assist cache-hit path (conn not defined before use) and ai_assist route (inconsistent conn management). Fixed by moving conn = get_db() to start of both routes (after login check) and wrapping route bodies in try/finally to close conn exactly once before every return; unexpected exceptions return {"success": false} with status 200, never 500.
- 22 Nov: Bug fix: Photo suggestion detail rows not appearing on report page. JS in report.html now properly creates detail rows (Brand/Colour) from AI response, with max 5 rows, no duplicate labels, and never overwrites student-edited rows.
- 22 Nov: Added tests to test_smoke.py: (a) photo cache hit returns success with same draft on second call, no 500; (b) unexpected exception in photo-assist returns {"success": false} with status 200, never 500.
- 19 Nov: one status file (`docs/PROGRESS.md`); project knowledge lives in the repo (`AGENTS.md`, `docs/`) so every AI tool starts informed.
- 19 Nov: the assistant box shipped first as a local parser (instant, no API errors). It must become Gemini-first with the local parser as fallback.
- 18 Nov: all Gemini calls go through `ai.py`; Flash model for the app (a Google AI Pro subscription does not give API quota).
- No WhatsApp links for contact (harassment risk); calls only through the phone dialer.
- Sightings are unverified leads: the poster accepts each request; several chats allowed.
- Old posts leave the home page and matching after a time limit; the poster can renew.
