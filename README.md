# SmartFind: AI-Powered Campus Lost & Found

A centralized website for Dayananda Sagar University where students can report lost and found items, replacing scattered WhatsApp groups.

## Features
- Student registration and login (passwords stored as secure hashes)
- Only logged-in students can report lost or found items
- Each post is linked to the student who created it
- View all reported items in one place
- Search by keyword and filter by lost or found
- Post owners can mark an item as returned
- SQLite database for stored data

## Planned
- AI-based matching between lost and found posts (TF-IDF and cosine similarity)
- Online deployment

## Tech Stack
- Backend: Python, Flask
- Database: SQLite
- Frontend: HTML, CSS (Jinja templates)
- AI (planned): scikit-learn

## How to Run
1. Install dependencies: `pip install -r requirements.txt`
2. Create the database: `python init_db.py`
3. Add the users table: `python add_users.py`
4. Start the app: `python app.py`
5. Open http://127.0.0.1:5000

Note: the database file (`smartfind.db`) is not stored in the repository, so steps 2 and 3 create it from scratch.

## Author
Harshwardhan Singh, 2nd year CSE, Dayananda Sagar University