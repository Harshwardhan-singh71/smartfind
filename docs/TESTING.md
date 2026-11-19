# SmartFind: test brief for an AI tester (18 Nov 2026)

You are helping test SmartFind, a campus Lost & Found website for a university project. It is a Flask + SQLite web app. Your job: find bugs, security problems and confusing behaviour. Report findings, do not rewrite the app unless asked.

## Quick start
Run `D:\PYTHON\python.exe test_smoke.py` first. It builds a temporary database and runs all checks. It does not touch the real database. Extend it with your own checks.

## Rules for you
- Use only fake test data. Never enter real names, phone numbers, ID cards or API keys.
- Do not print or ask for secrets (.env, admin.txt, smartfind.db contents).
- For every problem report: page/URL, the exact steps, what you expected, what happened, severity (blocker / bad / minor).
- Say clearly which checks you ran and which you could NOT run.

## Setup (Windows, PowerShell)
1. Clone: https://github.com/Harshwardhan-singh71/smartfind (branch `features`).
2. `pip install -r requirements.txt`
3. Run these in order: init_db.py, add_users.py, migrate_places.py, add_image_column.py, add_claims.py, add_must_change.py, add_notifications.py, add_match_alerts.py, add_messages.py, add_phone_calls.py, add_item_details.py, add_post_reports.py, add_ai_usage.py
4. Create `admin.txt` with one line: the admin email, e.g. admin@test.local
5. `python app.py` then open http://127.0.0.1:5000
6. There is no public sign-up. Create the admin account row first (use add_users.py or insert a user with that email), log in, open Manage users, and add test accounts like `Bob, bob@test.local, 9000000001`. Each gets a temporary password shown once.
7. The AI features need GEMINI_API_KEY in a `.env` file. Without it the site must still work (that is a test: the AI parts should fail quietly).
(For automated testing you can also use Flask's test client with a temporary database.)

## What the app should do (check each)
1. Access: every page except login requires login; there is no registration page; wrong passwords lock after 5 tries for 10 minutes; first login forces a password change; users stay logged in.
2. Posting: Lost, Found, Seen posts with title, description, category, place, date, time, optional photo (PNG/JPG/WEBP only). Check empty fields, very long text, HTML/script in text (must be escaped), huge or fake image files.
3. Home page: tabs All, Lost, Found, Seen, Resolved, Old; search; resolved items only under Resolved; posts older than Lost 45 / Found 60 / Seen 14 days only under Old (poster or admin can "Keep this post active").
4. Matching: when a lost and found post look alike (same category/words), the right owner gets a notification with a reason; no alert for different categories (unless very similar text), impossible dates, old posts, or the same pair twice; max 3 per post; "Not mine" dismisses. Matches page (/matches/<id>) shows Strong and Weaker lists with a "Why" line and is visible only to the poster and admin.
5. Claims (Found posts): another user can claim with an answer to the private question; can tick "Hide my name" (finder must see "Anonymous" on the item page, My activity and notifications; admin activity log keeps the real name); the finder accepts one claim, the others become rejected; you cannot claim your own post or a post with no owner; only the poster and the admin see the claims.
6. Sightings (Seen posts): "Ask about this sighting"; the poster can accept several requests; each accepted request opens a chat marked as an unverified sighting.
7. Chat: only the two people (and nobody else, including other logged-in users) can open /chat/<claim_id>, its /send, /new, /file and /calls URLs. Try IDOR: log in as a third user and guess IDs. Files up to 10 MB; executables and scripts (.exe, .bat, .html, .js ...) must be refused; downloads must be served with safe headers. Chat becomes read-only when the item is marked returned.
8. Calls: phone number is set on /profile (7 to 15 digits); in a chat each person can turn "Allow calls" on/off; the other person's call icon is green only when allowed; the number must not appear anywhere else; on a desktop browser the icon must refuse to dial; permission is deleted when the item is returned or the number is removed.
9. Reports: any user can report a post (not their own, once each); /admin/reports is admin-only (403 for others); Dismiss and Delete work.
10. Admin: Manage users (create, reset password, phone update), Activity log and Reports are admin-only; the admin account cannot be reset or listed.
11. Notifications: bell count, dropdown, mark all read, links open the right page.
12. Security checks: CSRF/forged POSTs from another user, direct URL access to /admin/*, /delete/<id>, /renew/<id>, /claim/<id>/decide as a non-owner; SQL injection in search and forms; XSS in titles, descriptions, chat messages and file names; path traversal in the chat file URL; session cookie flags; secrets in the repo (the repo is public: look for keys, .env, database, uploads); debug mode on in production.
13. AI helper (ai.py): with no key or no internet, the site must work normally; phone/email/card/ID numbers must be removed from any text before sending; one user is limited to 10 AI actions per day.
14. Phone layout: open on a phone (or 390px wide) and look for broken layouts, overflow, tiny buttons.

## Known limits (not bugs)
- The matcher is text-based (TF-IDF); photo matching is not built yet.
- Calls need a phone; WhatsApp or masked calling are intentionally not included.
- Gemini sometimes returns 503 "high demand"; ai.py retries once then falls back.
- The assistant bot (Report page) and photo auto-fill are still being built.
- CSRF protection may not be implemented yet: report it if you can forge a POST, with severity.

## Report format
A table: id, severity, area, steps, expected, actual, suggested fix. End with a list of what you could not test.
