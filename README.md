# SmartFind: AI-Powered Campus Lost & Found

A centralized website for Dayananda Sagar University where students can report lost, found and seen items in one place, replacing scattered WhatsApp groups.

## Features
- Student registration and login (passwords stored as secure hashes)
- Only logged-in students can post, and contact details are hidden from visitors
- Three post types: **Lost**, **Found** and **Seen** (spotted but not picked up)
- Tabs to switch between All, Lost, Found and Seen
- Exact place (pick from suggestions or type your own), date and time on every post
- Optional photo upload (PNG, JPG or WEBP, up to 20 MB)
- Keyword search across title, description, place and category
- AI matching: TF-IDF and cosine similarity suggest likely matches with a percentage score
- Post owners can mark an item as returned
- SQLite database for stored data

## Planned
- Notifications when a likely match is posted ("70% match, is this yours?")
- A "My Posts" page
- Matching that also scores place, date and time closeness
- AI image recognition to compare photos
- Online deployment

## Tech Stack
- Backend: Python, Flask
- Database: SQLite
- Frontend: HTML, CSS, Jinja templates
- AI: scikit-learn (TF-IDF, cosine similarity)

## How to Run
1. Install dependencies: `pip install -r requirements.txt`
2. Create the database: `python init_db.py`
3. Add users and extra columns: `python add_users.py`
4. Add place, date and time fields: `python migrate_places.py`
5. Add the image column: `python add_image_column.py`
6. Start the app: `python app.py`
7. Open http://127.0.0.1:5000

Run the scripts in the order shown. The database file (`smartfind.db`) and uploaded photos are not stored in the repository, because they can contain personal details, so steps 2 to 5 create the database from scratch.

## Project Structure
- `app.py`: Flask routes (home, report, login, register, matches, mark as returned)
- `matcher.py`: the AI matching function
- `templates/`: HTML pages built on a shared `base.html` layout
- `static/style.css`: the stylesheet

## Author
Harshwardhan Singh, 2nd year CSE, Dayananda Sagar University
Kartik Kamakhya, 2nd year CSE, Dayananda Sagar University