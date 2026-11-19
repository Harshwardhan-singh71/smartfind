# SmartFind status (keep under 40 lines)

## Built and working
- Login (admin creates accounts), photo-first posting with extra detail rows, Lost/Found/Seen, claims (anonymous option), chat with files, calls, notifications, match alerts, old-post handling, sightings, Report this post + admin Reports, PWA, footer safety note.
- ai.py is the only door to Gemini (limits, redaction, fallback).
- Report page assistant box (/ai/assist) is a LOCAL keyword parser, not Gemini.

## Next task
- Photo auto-fill (AI step C), or upgrade /ai/assist to Gemini via ai.ask_json with the local parser as fallback.

## Known issues
- Post titles are not stripped on save.
- Delete the real-ID test post before any demo.
- Gemini key is in .env (never commit).

## Run / test
- Run: D:\PYTHON\python.exe app.py
- Test: D:\PYTHON\python.exe test_smoke.py  (must pass after every change)