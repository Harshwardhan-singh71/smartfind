# SmartFind: instructions for any AI assistant (Claude, Cline, Cursor, Copilot, Gemini...)

SmartFind is a campus lost & found website (Flask + SQLite + Jinja + plain CSS, scikit-learn matching, Gemini for AI features) for a university course project. The owner is a beginner on Windows. The repo is PUBLIC.

## Read in this order (and nothing else until you need it)
1. This file.
2. `docs/PROGRESS.md`: what is done, the NEXT TASK, recent decisions. This is the source of truth for the current state.
3. `docs/PROJECT_CONTEXT.md`: history and the reasons behind decisions. Read only when you need the "why".
4. `docs/TESTING.md`: only when asked to test or review.
The owner should not have to explain the project again. If something is missing from these files, ask ONE short question, then add the answer to `docs/PROGRESS.md`.

## Hard rules
- Never commit, print, or ask for secrets: `.env` (Gemini key), `admin.txt`, `smartfind.db`, `static/uploads/`, `chat_uploads/`, passwords. Use fake test data only.
- All Gemini calls go through `ai.py` only. The site must keep working when the AI is down or the key is missing. Never send ID cards, wallets, card photos, or phone/ID numbers to the AI.
- Phone numbers are shown only to the other person in a chat who was allowed. Anonymous claimants stay hidden from the finder everywhere (the admin log keeps real names).
- No paid services. Branch `features` has the latest code (`main` is older).

## How to work with the owner
- One small step at a time. Give WHOLE-FILE or WHOLE-FUNCTION replacements, with closing lines included. No "add this somewhere below".
- Windows + PowerShell. Always `D:\PYTHON\python.exe` (plain `python` has no pip). The venv in the project folder is active.
- Remind the owner to stop the app (Ctrl+C) before editing, to run `git status` before committing, and to commit and push after each working step.
- Test your change yourself first: `D:\PYTHON\python.exe -m py_compile <file>` and `D:\PYTHON\python.exe test_smoke.py` (all checks on a temporary database; it must pass after every change). Add a check to `test_smoke.py` for each new feature. Then hand it over with: what changed, how to apply, how to test.
- Keep replies short and plain. Be honest when something cannot be done.

## Saving tokens (for you, the AI)
- Do not scan or summarise the whole repo. Use the file map below and open only the files the task needs.
- Do not re-read a file you already read this session. Do not paste large files back; show only what changed.
- Do not reformat, rename, or "improve" code the task did not ask about. No new documents or files unless asked.
- Make one change, check it, then move on. If the same fix fails twice, stop and ask the owner for the exact error text.
- Prefer small targeted checks (`py_compile`, one test) over running everything.

## File map
- `app.py`: all Flask routes and helpers.  `matcher.py`: TF-IDF matching + "why" lines.  `ai.py`: the only door to Gemini.
- `templates/`: Jinja pages (`base.html` layout).  `static/style.css`: styles.  `static/` also holds PWA manifest and icons.
- `init_db.py`, `add_*.py`, `migrate_places.py`: database setup scripts (order in README.md).
- `test_smoke.py`: the main test (temporary database).  `check_ai.py`, `test_gemini.py`, `test_matcher.py`: small checks.  `seed_demo.py`: fake demo data.  `.clineignore`: files Cline must not read.
- `README.md`: for humans.  `docs/`: for AI assistants.

## Before you finish a session
Update `docs/PROGRESS.md` (move finished work to Done, set the NEXT TASK, add new decisions; keep it under about 100 lines), run `py_compile` on changed files, list the changed files, and suggest a commit message.
