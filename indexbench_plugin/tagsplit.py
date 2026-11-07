"""Splits an item's MEGA tags into (kind, word) pairs: WD Tagger packs many words into
one tag (wd:1girl long_hair, chara:a chara:b), and exact matching needs them apart.
"""

GENERAL, CHARACTER, RATING, USER = 0, 1, 2, 3
KIND_NAMES = {GENERAL: "general", CHARACTER: "character", RATING: "rating", USER: "user"}

GENERAL_PREFIX = "wd:"
CHARACTER_PREFIX = "chara:"
RATING_PREFIX = "rating:"


def split_tags(tags):
    """[(kind, word, position)] in stored order, each (kind, word) once. Words are
    lowercased, as MEGA matches tags case-insensitively. position counts from 0 within
    the word's own tag, since WD Tagger writes the most confident words first."""
    result = []
    seen = set()

    def add(kind, word, position):
        key = (kind, word.lower())
        if word and key not in seen:
            seen.add(key)
            result.append((kind, key[1], position))

    for tag in tags or ():
        if tag.startswith(GENERAL_PREFIX):
            words = [w for w in tag[len(GENERAL_PREFIX):].split(" ") if w]
            for position, word in enumerate(words):
                add(GENERAL, word, position)
        elif tag.startswith(CHARACTER_PREFIX):
            words = [w[len(CHARACTER_PREFIX):] for w in tag.split(" ")
                     if w.startswith(CHARACTER_PREFIX)]
            for position, word in enumerate(w for w in words if w):
                add(CHARACTER, word, position)
        elif tag.startswith(RATING_PREFIX):
            add(RATING, tag[len(RATING_PREFIX):].strip(), 0)
        else:
            add(USER, tag.strip(), 0)
    return result
