"""Checks for photo_bot.local_colour (the local colour bot). No app, no database, no AI.
Run:  D:\\PYTHON\\python.exe test_photo_bot.py
"""
import io
import sys

from PIL import Image

from photo_bot import local_colour

results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + name)


def png(color, size=(200, 200), bg=None, box=None):
    """A PNG as bytes: solid colour, or a coloured square on a different background."""
    image = Image.new("RGB", size, bg or color)
    if bg and box:
        image.paste(color, box)
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def jpeg(color, size=(200, 200)):
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "JPEG")
    return out.getvalue()


check("solid blue gives Blue", local_colour(png((30, 90, 200))) == "Blue")
check("solid red gives Red", local_colour(png((200, 30, 30))) == "Red")
check("solid green gives Green", local_colour(png((30, 160, 60))) == "Green")
check("solid brown gives Brown", local_colour(png((150, 90, 40))) == "Brown")
check("solid black gives Black", local_colour(png((15, 15, 15))) == "Black")
check("solid white gives White", local_colour(png((250, 250, 250))) == "White")
check("brown square on a white background gives Brown (background ignored)",
      local_colour(png((150, 90, 40), bg=(255, 255, 255), box=(60, 60, 140, 140))) == "Brown")
check("blue square on a white background gives Blue",
      local_colour(png((30, 90, 200), bg=(255, 255, 255), box=(60, 60, 140, 140))) == "Blue")
check("works on a JPEG too", local_colour(jpeg((200, 30, 30))) == "Red")
check("garbage bytes give None, no crash", local_colour(b"this is not an image") is None)
check("empty bytes give None, no crash", local_colour(b"") is None)
check("None input gives None, no crash", local_colour(None) is None)

print()
if all(results):
    print(f"ALL {len(results)} CHECKS PASSED")
    sys.exit(0)
print(f"{results.count(False)} OF {len(results)} CHECKS FAILED")
sys.exit(1)
