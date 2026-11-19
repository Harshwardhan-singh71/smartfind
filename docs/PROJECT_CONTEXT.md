# SmartFind: project context (history and reasons)
For the current state and the NEXT TASK see PROGRESS.md; this file explains the history and the reasons behind decisions.

## 0. About this document and secrets
This file explains everything about the project: what it is, why each decision was made, what exists, what is planned. It deliberately contains NO secrets. These exist but are not shared and you must never ask for them: the Gemini API key (.env), the admin email (admin.txt), user passwords, the real database (smartfind.db), uploaded photos (static/uploads/) and chat files (chat_uploads/). The repo is public on GitHub, so nothing secret may ever be committed. If you need an AI key to test AI features, ask the owner to create a separate throwaway key; do not reuse the real one.

## 1. What and why
SmartFind is a campus-wide lost & found website for Dayananda Sagar University (Kanakpura, Bangalore). It is a university course project ("AI Powered Full Stack Development", 2nd-year CSE core B.Tech) built by a group of 3. The owner/lead developer is Harshwardhan Singh, a beginner on Windows; the code has been written step by step with Claude's help.
Problem: lost-and-found today means scattered WhatsApp groups and paper registers, so it is hard to search, to verify ownership, and to prevent false claims.
Users: students, faculty, campus security staff.
Original proposal (the course document): React/Next.js + Tailwind, Node/Express, MongoDB, Gemini/OpenAI Vision for image matching, Cloudinary, QR-code handoff, anonymous chat, smart categorisation. What was ACTUALLY built (and the teacher should be told): Flask + SQLite + Jinja templates + plain CSS + scikit-learn TF-IDF matching, and Gemini through the google-genai Python SDK for new AI features. QR handoff was replaced by the claim-and-accept flow; Cloudinary was replaced by local uploads.
The teacher's required features: notifications; contact click-through (name may be anonymous, phone optional); in-app chat with file sharing and a call option; a deployable app (a website is fine) with photo-first quick posting and stay-logged-in. Design polish last. Deployment only after asking the teacher. AI integration last.

## 2. Timeline (past)
1. Basic app: post Lost/Found, home list, search, SQLite.
2. Matching: TF-IDF text similarity plus category/place bonus (matcher.py: weights text 0.8, category 0.1, place 0.1).
3. Structured places, photo upload, resolved state ("Mark as returned").
4. Accounts: login-only, admin-created accounts, temporary password and forced change, login lockout, admin identified by email in admin.txt.
5. Claims system ("This is mine" + private question), finder accepts one claim, activity page, admin activity log.
6. Notifications (bell, dropdown, page).
7. Match alerts with anti-spam rules.
8. Chat between finder and accepted claimant, then file sharing (any type up to 10 MB except executables), then optional phone numbers with per-chat "Allow calls", a profile page, anonymous claims.
9. Sightings (Seen posts): "Ask about this sighting".
10. Safety and housekeeping: Report this post + admin Reports page, footer safety note, PWA manifest/icons, stay-logged-in (about 60 days), photo-first report form with detail rows, Old tab with time limits and "Keep this post active", match tiers with "Why" lines.
11. AI groundwork: Gemini connected and tested; ai.py safe helper; per-user daily limit table.
Earlier an IDE agent (Antigravity) also touched the code (photo-first form, stay-logged-in, PWA, reports); its changes were reviewed and are in the repo.

## 3. Design decisions and why (the reasoning matters)
- Login mandatory, admin-created accounts only, no public registration: prevents spam/outsiders and keeps contact info private. Matches and contact info are never public.
- "Two owners" / false-claim problem: finder adds a private question; claimants answer; finder accepts exactly one claimant (others rejected); chat opens only with the accepted claimant; valuables can be marked "at the security desk"; every claim and decision is logged for disputes. Accepting a claim does NOT mark the item returned; the finder does that after handover.
- Match alert policy (to avoid spamming everyone): threshold 40%; alert only if same category OR text similarity >= 70%; found date cannot be earlier than lost date (1 day slack); max 3 alerts per new post; one alert per lost/found pair ever; "Not mine" dismissal; posts past the time limit are excluded. Matches page shows Strong (>=60%) and Weaker possibilities, each with a plain "Why" line.
- Sightings are unverified leads: the poster accepts or declines each request, can talk to several people, and the chat shows a warning. No private question because nothing is handed over.
- Privacy of contact details: phone numbers belong to accounts, are shown only to the other person in a chat who was allowed, and only through a call icon that works on phones (tel: link). On desktop it refuses. No WhatsApp links on purpose (harassment risk). Permission is deleted when the item is returned. Anonymous claimants are hidden from the finder on every page and in the activity search; admin log keeps real names.
- Chat files: stored outside the public static folder, served only to the two chat members, blocked extension list, nosniff header, 10 MB cap.
- Why polling chat (4 s) and not websockets: simplicity for a beginner and for free hosting.
- Old posts: Lost 45 / Found 60 (the holding period) / Seen 14 days, then the Old tab. A found item past 60 days should go to the security desk or university lost-and-found.
- Why Flash models for AI: the app calls the AI per user action, all users share one free key, Flash is faster with higher free limits. A Google AI Pro subscription does not give API quota (only AI Studio web use).
- AI safety rules: AI features must be optional (site works without them); every call goes through ai.py; redact phone/email/card/ID numbers before sending; never send photos of ID cards, wallets or cards; free tier prompts may be used by Google; 10 AI actions per user per day; one retry on 503/504; pause on 429.
- Why not Render free for hosting: filesystem is ephemeral (SQLite and uploads would be lost). PythonAnywhere free is the likely host (one web app, small daily CPU, outbound allowlist includes googleapis.com, needs monthly renewal). Plan B is a live demo from the owner's laptop.

## 4. Architecture (present)
- app.py: all Flask routes, session handling, before_request login gate, error handlers, context processors (is_admin, unread notifications, open report count).
- matcher.py: find_matches(target, candidates, top_n, min_score) returns (item, percent); why_matched(target, candidate) returns reasons.
- ai.py: ask_text / ask_json / redact / allow_use / uses_left / is_available; last_error for debugging.
- templates/ (Jinja, base.html layout, navy+orange theme), static/style.css, PWA manifest and icons.
- Setup scripts create tables (see test brief for the order). Tables: items, users(name,email,password_hash,must_change_password,phone), claims(+anonymous), events, notifications, match_alerts, messages, call_consent, item_details, post_reports, ai_usage.
- Admin = the email in admin.txt. Secret key from SMARTFIND_SECRET_KEY. The dev server runs with debug on; it must be off in production.

## 5. Current status and known issues
Working and tested by the owner and by automated Flask test-client checks: everything in section 2. 
Open items: titles are not trimmed on save; possibly no CSRF tokens (verify); free-tier Gemini returns 503 "high demand" sometimes (handled by retry/fallback); README and docs need upkeep; add_allowed_emails.py is unused; sample owner-less items exist from init_db.py; a real student-ID photo post existed in the owner's test data and must be deleted before any demo; design on phones not yet polished.

## 6. Future plans (in order)
AI step B: assistant bot on the Report page (user writes plain words, Gemini returns a JSON draft: status, title, category, place, description, date/time; fills the form; user confirms; fallback note if AI fails).
AI step C: photo auto-fill (title/category/colour from a photo; tick box for "contains ID/card" to skip the AI).
AI step D: smarter matching with photos/descriptions; advisory claim check for finders (answer looks consistent/inconsistent, the finder still decides).
AI step E: safety scan of posts (phone/ID numbers, abuse) feeding the admin Reports page.
Then: design polish and phone layout, cleanup (delete real-ID test posts, secret key, final README), deployment after asking the teacher, teammates added last.
Possible later ideas: serial-number private field, block button, QR handoff, holding-period admin actions.

## 7. How the owner wants to work (for any AI helping)
One small step at a time; whole-file or whole-function replacements; tell the owner to stop the app (Ctrl+C) before editing; use D:\PYTHON\python.exe (plain `python` is MSYS2 with no pip); test before sending; commit and push after each working step; be honest about limits; keep answers short and plain. Branch `features` has the latest code (main is older). Do not suggest paid services; the owner cannot afford them.

## 8. What your review should deliver
Run the checks in SmartFind_test_brief.md. Report bugs, security holes (IDOR, XSS, CSRF, path traversal, secrets in the repo, privacy leaks of phone numbers or anonymous names) and confusing behaviour, ranked by severity, with exact steps. Say what you could not test. Do not change the owner's files unless asked.
