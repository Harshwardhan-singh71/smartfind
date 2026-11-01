from matcher import find_matches

lost_item = {
    "title": "Black leather wallet",
    "description": "Black wallet with ID card and some cash inside",
    "category": "Wallet",
    "location": "Library",
}

found_items = [
    {"title": "Blue water bottle", "description": "Milton bottle with a sticker",
     "category": "Bottle", "location": "Canteen"},
    {"title": "Wallet found", "description": "Black wallet with a few cards",
     "category": "Wallet", "location": "Library"},
    {"title": "Casio calculator", "description": "Scientific calculator fx-991EX",
     "category": "Electronics", "location": "Block 2"},
]

for item, percent in find_matches(lost_item, found_items):
    print(f"{percent}% match -> {item['title']} ({item['location']})")