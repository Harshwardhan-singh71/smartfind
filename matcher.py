from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def item_text(item):
    # Title is repeated so it counts more than the other fields.
    return " ".join([
        item["title"] or "",
        item["title"] or "",
        item["description"] or "",
        item["category"] or "",
        item["location"] or "",
    ])


def find_matches(target, candidates, top_n=3, min_score=0.1):
    """Return up to top_n (item, percent) pairs, best match first."""
    if not candidates:
        return []

    texts = [item_text(target)] + [item_text(c) for c in candidates]

    try:
        matrix = TfidfVectorizer(stop_words="english").fit_transform(texts)
    except ValueError:
        return []

    scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    ranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)

    return [
        (item, round(float(score) * 100))
        for item, score in ranked[:top_n]
        if score >= min_score
    ]