import re

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# How the final score is built (adds up to 1.0)
W_TEXT = 0.8        # title and description similarity
W_CATEGORY = 0.1    # bonus for the same category
W_PLACE = 0.1       # bonus for the same place


def field(item, name):
    """Safely read a field from a database row or a dict."""
    try:
        value = item[name]
    except (KeyError, IndexError):
        return ""
    return (value or "").strip()


def field_similarity(target_text, candidate_texts):
    """TF-IDF cosine similarity of one text against a list of texts."""
    if not target_text:
        return [0.0] * len(candidate_texts)
    texts = [target_text] + candidate_texts
    try:
        matrix = TfidfVectorizer(stop_words="english").fit_transform(texts)
    except ValueError:
        return [0.0] * len(candidate_texts)
    return cosine_similarity(matrix[0:1], matrix[1:]).flatten().tolist()


def find_matches(target, candidates, top_n=3, min_score=0.12):
    """Return up to top_n (item, percent) pairs, best match first."""
    if not candidates:
        return []

    title_sims = field_similarity(
        field(target, "title"), [field(c, "title") for c in candidates]
    )
    desc_sims = field_similarity(
        field(target, "description"), [field(c, "description") for c in candidates]
    )

    target_category = field(target, "category").lower()
    target_place = field(target, "place").lower()

    results = []
    for candidate, title_sim, desc_sim in zip(candidates, title_sims, desc_sims):
        # Descriptions count most. If either post has none, fall back to the title.
        has_descriptions = field(target, "description") and field(candidate, "description")
        text_score = 0.65 * desc_sim + 0.35 * title_sim if has_descriptions else title_sim

        # Bonuses only help when the text is already somewhat similar.
        if text_score < 0.05:
            continue

        category_bonus = 1.0 if target_category and target_category == field(candidate, "category").lower() else 0.0
        place_bonus = 1.0 if target_place and target_place == field(candidate, "place").lower() else 0.0

        score = W_TEXT * text_score + W_CATEGORY * category_bonus + W_PLACE * place_bonus
        if score >= min_score:
            results.append((candidate, round(score * 100)))

    results.sort(key=lambda pair: pair[1], reverse=True)
    return results[:top_n]


def keywords(item):
    """The meaningful words in an item's title and description."""
    text = f"{field(item, 'title')} {field(item, 'description')}".lower()
    words = re.findall(r"[a-z0-9]+", text)
    return {w for w in words if len(w) > 2 and w not in ENGLISH_STOP_WORDS}


def why_matched(target, candidate, max_words=4):
    """Short plain-language reasons why two posts look alike (for the user to read)."""
    reasons = []
    category = field(target, "category")
    if category and category.lower() == field(candidate, "category").lower():
        reasons.append(f"same category ({category})")
    place = field(target, "place")
    if place and place.lower() == field(candidate, "place").lower():
        reasons.append(f"same place ({place})")
    shared = sorted(keywords(target) & keywords(candidate))
    if shared:
        reasons.append("similar words: " + ", ".join(shared[:max_words]))
    return reasons
