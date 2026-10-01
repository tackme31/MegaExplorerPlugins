"""Turns model probabilities into MEGA tags (docs/SPEC.md §1)."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path

GENERAL_PREFIX = "wd:"
RATING_PREFIX = "rating:"
CHARACTER_PREFIX = "chara:"
PLUGIN_PREFIXES = (GENERAL_PREFIX, RATING_PREFIX, CHARACTER_PREFIX)

# MegaClient::MAX_NUMBER_TAGS / MAX_TAGS_SIZE (bytes of all tags joined with ',').
MEGA_MAX_TAGS = 10
MEGA_MAX_TAGS_BYTES = 3000

CATEGORY_GENERAL = 0
CATEGORY_CHARACTER = 4
CATEGORY_RATING = 9

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}
VIDEO_EXTENSIONS = {"mp4", "avi", "mkv", "webm", "mov", "wmv", "flv", "m4v", "gif"}


@dataclass
class Config:
    repo_id: str = "SmilingWolf/wd-eva02-large-tagger-v3"
    thresh_general: float = 0.30
    thresh_character: float = 0.50
    thresh_rating: float = 0.40
    max_general_bytes: int = 2000


def load_config(path):
    """Defaults, overridden by whatever keys config.json has (a missing file is fine)."""
    config = Config()
    path = Path(path)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in fields(Config)}
        for key, value in data.items():
            if key in known:
                setattr(config, key, value)
    return config


def is_taggable(name):
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return ext in IMAGE_EXTENSIONS or ext in VIDEO_EXTENSIONS


def is_plugin_tag(tag):
    return tag.startswith(PLUGIN_PREFIXES)


def has_been_tagged(tags):
    return any(tag.startswith(GENERAL_PREFIX) for tag in tags or ())


def tag_changes(existing_tags, new_tags):
    """(add, remove) that turn the plugin's tags among existing_tags into new_tags,
    leaving the user's own tags and any tag already right alone."""
    old = [t for t in existing_tags or () if is_plugin_tag(t)]
    return [t for t in new_tags if t not in old], [t for t in old if t not in new_tags]


def _tag_bytes(tags):
    return len(",".join(tags).encode("utf-8"))


def build_tags(probs, names, categories, config, existing_tags=()):
    """The tags to add: wd:, then rating:, then one tag of every chara: above
    the threshold, best first and space-separated like the wd: one.

    Fits them next to existing_tags within MEGA's tag count and byte limits,
    dropping the lowest-scoring characters first, then the rating, then the
    lowest-scoring general tags. Returns [] when not even the wd: tag fits.
    """
    def above(category, threshold):
        picked = [
            (float(probs[i]), names[i])
            for i in range(len(names))
            if categories[i] == category and probs[i] >= threshold
        ]
        picked.sort(reverse=True)
        return [name for _, name in picked]

    general = above(CATEGORY_GENERAL, config.thresh_general)
    ratings = above(CATEGORY_RATING, config.thresh_rating)[:1]
    characters = above(CATEGORY_CHARACTER, config.thresh_character)

    def general_tag(words):
        return GENERAL_PREFIX + " ".join(words)

    while general and len(general_tag(general).encode("utf-8")) > config.max_general_bytes:
        general.pop()

    def assemble():
        tags = [general_tag(general)] + [RATING_PREFIX + r for r in ratings]
        if characters:
            tags.append(" ".join(CHARACTER_PREFIX + c for c in characters))
        return tags

    user_tags = [t for t in existing_tags or () if not is_plugin_tag(t)]
    if len(user_tags) + 1 > MEGA_MAX_TAGS:
        return []
    while (len(user_tags) + len(assemble()) > MEGA_MAX_TAGS
           or _tag_bytes(user_tags + assemble()) > MEGA_MAX_TAGS_BYTES):
        if characters:
            characters.pop()
        elif ratings:
            ratings.pop()
        elif general:
            general.pop()
        else:
            return []
    return assemble()
