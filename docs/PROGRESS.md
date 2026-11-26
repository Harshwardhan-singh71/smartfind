# SmartFind: progress (the source of truth for the current state)
Last updated: 23 Nov 2026. Update this file at the end of every working session. (It replaces the old STATUS.md.)

## Done
- First-run database setup: a downloaded copy now detects a missing `items` table and runs the existing schema scripts automatically before serving Flask; existing databases are left untouched.
- Responsive hero atmosphere: moved the campus photo, glow and bottom fade from the fixed-width hero container to a full-viewport layer, removing the visible rectangular cutoff in both themes and allowing the effect to resize with the preview.
- Hero action cleanup: removed the diagonal grid/colour block behind the report buttons, confined campus photography to the right side, and versioned the stylesheet URL so browsers load the correction instead of stale CSS.
- Theme polish: fixed hero/menu clipping, removed competing reveal systems and hidden-content animation states, softened the light-mode section transition, and rebalanced display/body typography and spacing.
- Persistent dark/light themes: navigation switch remembers the choice, updates the whole site, uses a smooth circular reveal when supported, respects reduced motion, and keeps the cinematic design in a lighter DSU-blue palette.
- Full-site visual system: extended the cinematic dark/glass design from the homepage to report, item, activity, matches, chat, notifications, profile, login and admin screens, including forms, tables, alerts and mobile layouts.
- Reference-led homepage refinement: combined AW Media-inspired cinematic depth, glass panels, ambient lighting, numbered storytelling and progressive scroll motion with Tasa-style clarity, contrast, reduced-motion support and direct campus-service language.
- Recent reports: text-only posts use a compact identity strip instead of reserving a full photo area, and no-photo cards no longer stretch to match photo cards.
- Homepage visual redesign: authentic DSU campus-service identity using the real campus photo, editorial hero, live board summary, clearer recovery process, responsive report grid, and restrained motion. Existing routes and behavior are unchanged.
- Accessibility polish: mobile menu and notifications now report open/closed state, close with Escape and restore keyboard focus; the rotating home headline respects reduced-motion preferences.
- Figma Make import bootstrap: `.figma/make/install` installs requirements and initializes a missing local database; `.figma/make/dev` serves Flask on the assigned preview port. `figma make verify-bootstrap` passes.
- Phone menu: hamburger menu at max-width 700px, vertical list, 44px links, bell dropdown constrained to `calc(100vw - 24px)`.
- Safety net: `html, body { max-width: 100%; overflow-x: hidden; }`, `overflow-wrap: anywhere` on nav links.
- Footer fix: `body` column flex with `min-height: 100vh` and `main` flex: 1.
- Item page actions: full-width buttons, min-height 44px, 10px gap on phones.

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
- Figma deploy and deploy-preview do not support this stateful Flask + SQLite app as a static site. Deploy-preview is explicitly skipped; production remains planned for a Python host such as PythonAnywhere.
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
