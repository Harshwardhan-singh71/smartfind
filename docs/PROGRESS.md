# SmartFind: progress (the source of truth for the current state)
Last updated: 19 Nov 2026. Update this file at the end of every working session. (It replaces the old STATUS.md.)

## NEXT TASK: upgrade the Report page assistant to Gemini (AI step B2)
Today `/ai/assist` (app.py) is a LOCAL keyword parser: no AI. For the course's AI requirement, make it use Gemini first and keep the local parser as the fallback.
1. In `ai_assist`: after the login check, call `ai.allow_use(conn, user_id)`. If the allowance is used up, use the local parser and tell the user.
2. Ask `ai.ask_json(prompt)` for the same draft keys the route already returns: status (lost/found/seen), title, category (one of Wallet, Bottle, Electronics, Books, ID Card, Keys, Clothing, Other), place (one of the campus places in the code), place_details, event_date (YYYY-MM-DD; resolve "yesterday" with today's date), event_time, description, details. Validate every value against the allowed lists. Any `None` or invalid answer means: run the local parser instead.
3. Return the draft plus a field saying which source made it ("ai" or "basic") and the uses left today. The page should show a small note when the basic version was used. Never auto-post.
4. Add checks to `test_smoke.py` with a fake `ai` module: AI draft is used when valid; invalid or None falls back; the daily limit falls back; logged-out is refused.
5. Known weakness of the local parser: status words like "has"/"have" can mark a post as found by accident; check this against the AI version.

## After that (in order)
- AI step C: photo auto-fill (title/category/colour from a photo; tick box "this photo has an ID or card" skips the AI; never send IDs).
- AI step D: smarter matching using photos/descriptions; advisory claim check for the finder.
- AI step E: safety scan of posts (phone/ID numbers, abuse) feeding the admin Reports page.
- Design polish and phone layout; cleanup (delete real-ID test posts, secret key); keep README current.
- Deployment after asking the teacher: PythonAnywhere free (Plan A), laptop demo (Plan B). Render free is unsuitable (ephemeral disk).
- Teammates are added last.

## Done (all tested; `test_smoke.py` passes 22/22)
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
- 19 Nov: one status file (`docs/PROGRESS.md`); project knowledge lives in the repo (`AGENTS.md`, `docs/`) so every AI tool starts informed.
- 19 Nov: the assistant box shipped first as a local parser (instant, no API errors). It must become Gemini-first with the local parser as fallback.
- 18 Nov: all Gemini calls go through `ai.py`; Flash model for the app (a Google AI Pro subscription does not give API quota).
- No WhatsApp links for contact (harassment risk); calls only through the phone dialer.
- Sightings are unverified leads: the poster accepts each request; several chats allowed.
- Old posts leave the home page and matching after a time limit; the poster can renew.
