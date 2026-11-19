# SmartFind rules for Cline
- Follow AGENTS.md in the repo root. At the start of every task read AGENTS.md and docs/PROGRESS.md only. Do not scan the repo.
- Open only the files the task needs. Do not re-read files. Do not reformat or rewrite unrelated code. Do not create new files unless asked.
- One small change at a time: edit, run `D:\PYTHON\python.exe -m py_compile <file>`, then `D:\PYTHON\python.exe test_smoke.py` (must pass), then continue. If the same error happens twice, stop and ask me for the exact error text.
- A new table needs an add_*.py script, and it goes in the README setup order.
- Never read or print .env, admin.txt, smartfind.db, static/uploads or chat_uploads.
- Keep replies short. At the end, update docs/PROGRESS.md and suggest a commit message.
