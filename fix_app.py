"""Small script to add mode=basic support to app.py"""
content = open("c:\\projects\\smartfind_v3\\app.py").read()

old = """photo_bytes = photo.read()
    if len(photo_bytes) > 4 * 1024 * 1024:
        print("[photo-assist] refusal: too big")
        return jsonify({"success": False})

    conn = get_db()"""

new = """photo_bytes = photo.read()
    if len(photo_bytes) > 4 * 1024 * 1024:
        print("[photo-assist] refusal: too big")
        return jsonify({"success": False})

    # mode=basic: instant local colour, no AI call, no allowance used
    if request.form.get("mode") == "basic":
        from photo_bot import local_colour
        colour = local_colour(photo_bytes)
        if colour is None:
            print("[photo-assist] basic mode: local_colour returned None")
            return jsonify({"success": False})
        print(f"[photo-assist] basic mode: colour={colour}")
        return jsonify({
            "success": True,
            "draft": {
                "title": "",
                "category": "Other",
                "details": [{"label": "Colour", "value": colour}],
                "description": "",
            },
        })

    conn = get_db()"""

if old in content:
    content = content.replace(old, new)
    open("c:\\projects\\smartfind_v3\\app.py", "w").write(content)
    print("Done: app.py updated")
else:
    print("Old text NOT found - checking what's there...")
    # Print the relevant section
    for i, line in enumerate(content.split("\n"), 1):
        if "photo_bytes" in line or "conn = get_db" in line:
            print(f"{i}: {line}")