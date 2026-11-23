# SmartFind: AI-Powered Campus Lost & Found

A centralized website for Dayananda Sagar University where students and staff report lost, found and seen items in one place, replacing scattered WhatsApp groups. Likely matches are suggested automatically, and owners are verified before an item is handed back.

## Features
- **Private, login-only site.** No public registration. The admin creates accounts (name, email, optional phone). Each user gets a temporary password and must choose their own at first login. Failed logins are rate-limited, and users stay signed in for weeks.
- **Three post types:** Lost, Found and Seen. Each post has a category, exact place, date, time and an optional photo. Home page tabs: All, Lost, Found, Seen, Resolved and Old. Keyword search.
- **Old posts:** unreturned posts leave the home page after a time limit (Lost 45 days, Found 60 days as a holding period, Seen 14 days) and move to the Old tab. They are skipped in matching. The poster can keep a post active with one click, and an old found item prompts handing it to the security desk.
- **Photo-first report form** with extra optional detail rows (brand, colour and more).
- **AI matching:** TF-IDF and cosine similarity (scikit-learn) score lost against found posts, boosted by matching category and place. The matches page splits results into Strong matches (60% and above) and Weaker possibilities, and each match has a plain-language "Why" line (same category, same place, shared words). Match alerts go only to the right owner, follow date and category rules, never repeat, include the reason, and can be dismissed with "Not mine".
- **AI Quick-Fill:** type a sentence ("I lost my black earphones near the library yesterday") and the report form fills itself in.
- **Photo suggestion:** choose a photo and the title, category, brand, colour and a short description are suggested automatically. Photos marked as personal documents (ID cards, bank cards) are never sent to the AI.
- **Safe ownership checks:** the finder can add a private question to a Found post. People tap "This is mine" and answer it (optionally hiding their name, which stays hidden from the finder everywhere but is kept in the admin log). The finder accepts one claim. Valuable items can be marked "at the security desk".
- **Sightings:** on a Seen post, people tap "Ask about this sighting". The person who saw it accepts or declines each request, and can chat with several people. The chat is labelled as an unverified sighting.
- **Private chat** between the finder and the accepted claimant only, with photo and file sharing (any type up to 10 MB except programs, scripts and web pages). Files are stored outside the public folder. The chat becomes read-only once the item is returned.
- **Optional calls:** users can add a phone number on their profile and switch on "Allow calls" per chat. The other person sees a call icon that opens the phone dialer on mobile. Numbers are never shown anywhere else, and permission is removed when the item is returned.
- **Notifications:** a bell with unread count, a dropdown, and a full notifications page.
- **My activity:** my posts, claims I sent, claims on my items, with search and filters.
- **Admin tools:** manage users (with optional phone numbers) and reset passwords, an activity log of claims and decisions for disputes, delete posts, and a Reports page that lists reported posts with the reasons and lets the admin dismiss the reports or delete the post.
- **Safety:** a "Report this post" button, a safety note in the footer, and an installable web app (Add to Home Screen).
- **Works on phones:** a Menu button replaces the long top bar, buttons are full width, and nothing scrolls sideways.

## How the AI is designed
Nobody waits for AI. Every AI feature shows an instant local result first (a built-in text parser, and a local colour detector for photos). Google Gemini only improves that result in the background, with a short timeout, and any failure is silent. The site works fully with the AI switched off.

- Free-tier protection: each user gets 10 AI requests per day, and the whole site shares a daily budget (450). A failed call gives the allowance back.
- A circuit breaker pauses Gemini for 30 seconds after two failures in a row, so slow moments never pile up.
- Repeated text or photos are answered from a cache and use no AI request.
- Emails, phone numbers, card and ID numbers are removed from text before it is sent to Gemini.

## Tech Stack
- Backend: Python, Flask
- Database: SQLite
- Frontend: HTML, CSS, Jinja templates
- Matching: scikit-learn (TF-IDF, cosine similarity)
- AI assistant: Google Gemini API (`google-genai`), optional
- Photos: Pillow (local colour detection)

## How to Run
1. Install dependencies: `pip install -r requirements.txt`
2. Create the database and tables by running these scripts **in this order**:
   ```
   python init_db.py
   python add_users.py
   python migrate_places.py
   python add_image_column.py
   python add_claims.py
   python add_must_change.py
   python add_notifications.py
   python add_match_alerts.py
   python add_messages.py
   python add_phone_calls.py
   python add_item_details.py
   python add_post_reports.py
   python add_ai_usage.py
   ```
3. Create a file named `admin.txt` containing the admin's email (one line). This file is never committed.
4. Optional: set a real secret key before deploying: `SMARTFIND_SECRET_KEY=<long random text>`. When serving over HTTPS also set `SMARTFIND_HTTPS=1`.
5. Start the app: `python app.py`, then open http://127.0.0.1:5000
6. Log in as the admin, open **Manage users**, and create accounts (`Name, email, phone`, one per line). Users can add or change their own number later on the **My profile** page (click "Hi, name").
7. Optional, for the Gemini upgrade: create a file named `.env` containing `GEMINI_API_KEY=your-key` (get a free key at aistudio.google.com). You can also add `GEMINI_MODEL=gemini-3.5-flash-lite`. `.env` is never committed, and the site works normally without it.

The database (`smartfind.db`), uploaded photos, chat files and `admin.txt` are not stored in the repository because they contain personal details.

## Tests
Run each from the project folder:
```
python test_matcher.py
python test_smoke.py
python test_ai_limits.py
python test_photo_bot.py
```
`test_smoke.py` needs `admin.txt` to exist. None of the tests call the real Gemini API.

## Project Structure
- `app.py`: all Flask routes
- `matcher.py`: the AI matching function
- `ai.py`: the only place that talks to Gemini (limits, cache, circuit breaker)
- `photo_bot.py`: local colour detection from a photo
- `templates/`: HTML pages built on `base.html`
- `static/`: stylesheet, icons, web app manifest
- `add_*.py`, `init_db.py`, `migrate_places.py`: database setup scripts
- `seed_demo.py`: optional fake demo items
- `test_*.py`: automated checks

## Planned
- Smarter matching that also compares photos and descriptions
- Advisory claim check for the finder
- Safety scan for posts that show phone or ID numbers
- Online deployment

## Authors
Harshwardhan Singh, 2nd year CSE, Dayananda Sagar University
Kartik Kamakhya, 2nd year CSE, Dayananda Sagar University
