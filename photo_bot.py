"""Local photo colour bot — works instantly, no AI needed.

Provides `local_colour(image_bytes) -> colour name or None`.
Errors always return None; never raise.
Never saves or logs the photo.
"""
import io

from PIL import Image

COLOUR_NAMES = [
    "Black", "White", "Grey", "Red", "Orange", "Yellow",
    "Green", "Blue", "Purple", "Pink", "Brown", "Beige",
]


def _rgb_to_hsv(r, g, b):
    """Convert RGB (0-255) to HSV (H: 0-360, S: 0-1, V: 0-1)."""
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0
    mx = max(r_norm, g_norm, b_norm)
    mn = min(r_norm, g_norm, b_norm)
    df = mx - mn
    if mx == mn:
        h = 0
    elif mx == r_norm:
        h = (60 * ((g_norm - b_norm) / df % 6))
    elif mx == g_norm:
        h = (60 * ((b_norm - r_norm) / df + 2))
    else:
        h = (60 * ((r_norm - g_norm) / df + 4))
    if h < 0:
        h += 360
    if mx == 0:
        s = 0
    else:
        s = df / mx
    v = mx
    return h, s, v


def _name_from_hsv(h, s, v):
    """Map HSV values to a colour name using simple thresholds."""
    # Value too low => black/dark
    if v < 0.2:
        return "Black"
    # Very desaturated => grey or white
    if s < 0.15:
        if v > 0.9:
            return "White"
        return "Grey"
    # High brightness + desaturated => white
    if v > 0.9 and s < 0.3:
        return "White"

    # Brown: medium v and medium s, reddish hue
    if 0.3 < v < 0.7 and s < 0.8 and h < 30:
        return "Brown"

    hue = h  # 0-360

    # Red: 0-30 (covers red; brown already handled above)
    if hue < 30:
        return "Red"
    # Orange: 30-50
    if hue < 50:
        return "Orange"
    # Yellow: 50-70
    if hue < 70:
        return "Yellow"
    # Green: 70-150
    if hue < 150:
        return "Green"
    # Blue: 150-250
    if hue < 250:
        return "Blue"
    # Purple: 250-280
    if hue < 280:
        return "Purple"
    # Pink/Red: 280-340 (wrap-around from 0)
    if hue >= 330:
        return "Pink"
    return "Red"


def local_colour(image_bytes):
    """Return a colour name from the list, or None on any error.

    Method:
    - Open image with Pillow, convert to RGB
    - Resize thumbnail to 64x64
    - Take the most common colour along the image border as the background
      and ignore pixels close to it
    - Take the most common remaining colour and map it to a name using HSV thresholds
    - Any error returns None, never raises
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        img.thumbnail((64, 64))

        w, h = img.size
        pixels = list(img.getdata())

        # Collect border pixels (first/last row, first/last column)
        border_pixels = []
        for y in range(h):
            for x in range(w):
                if x == 0 or x == w - 1 or y == 0 or y == h - 1:
                    border_pixels.append(pixels[y * w + x])

        if not border_pixels:
            return None

        # Find most common border colour (the "background")
        border_counts = {}
        for px in border_pixels:
            border_counts[px] = border_counts.get(px, 0) + 1
        background = max(border_counts, key=border_counts.get)

        # Collect non-border pixels, ignore those close to background colour
        non_bg = []
        for y in range(h):
            for x in range(w):
                if x == 0 or x == w - 1 or y == 0 or y == h - 1:
                    continue
                px = pixels[y * w + x]
                # Skip pixels very close to background (small delta)
                if abs(px[0] - background[0]) <= 10 and \
                   abs(px[1] - background[1]) <= 10 and \
                   abs(px[2] - background[2]) <= 10:
                    continue
                non_bg.append(px)

        # If all non-border pixels were filtered out (solid colour image case),
        # fall back to using all non-border pixels without filtering
        if not non_bg:
            non_bg = [pixels[y * w + x] for y in range(h) for x in range(w)
                      if not (x == 0 or x == w - 1 or y == 0 or y == h - 1)]

        if not non_bg:
            return None

        # Find most common non-border colour
        non_bg_counts = {}
        for px in non_bg:
            non_bg_counts[px] = non_bg_counts.get(px, 0) + 1
        most_common = max(non_bg_counts, key=non_bg_counts.get)

        h, s, v = _rgb_to_hsv(*most_common)
        name = _name_from_hsv(h, s, v)

        # Verify the name is in our list; fallback
        if name not in COLOUR_NAMES:
            name = None

        return name

    except Exception:
        return None