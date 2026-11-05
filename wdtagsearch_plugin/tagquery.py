"""The tag index and query building, kept free of tkinter and the app connection.

WD Tagger packs several words into one MEGA tag ("wd:1girl solo ...",
"chara:a chara:b"), so suggestions are per word, while the match count runs the
app's own rule on the stored tags: every term must be a case-insensitive
substring of some tag on the file. The same rule picks the files a search shows.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass

MAX_SUGGESTIONS = 50
GENERAL_PREFIX = "wd:"
CHARACTER_PREFIX = "chara:"
RATING_PREFIX = "rating:"
RATINGS = ("general", "sensitive", "questionable", "explicit")
# What the app's query parser splits words at; a term holding one needs quotes.
QUERY_SPACES = (" ", "\t", "　")


@dataclass(frozen=True)
class File:
    handle: str
    name: str
    mtime: int
    has_thumbnail: bool


def words_of(tag):
    """(term, kind) for each searchable word in one stored tag; ratings are separate."""
    if tag.startswith(GENERAL_PREFIX):
        return [(word, "general") for word in tag[len(GENERAL_PREFIX):].split(" ") if word]
    if tag.startswith(CHARACTER_PREFIX):
        return [(word, "chara") for word in tag.split(" ")
                if word.startswith(CHARACTER_PREFIX) and len(word) > len(CHARACTER_PREFIX)]
    if tag.startswith(RATING_PREFIX):
        return []
    return [(tag, "tag")]


class TagIndex:
    def __init__(self):
        self.tags = []      # per file: its stored tags, lower-cased
        self.entries = []   # per file: the File given to add(), or None
        self.files_by_word = defaultdict(set)
        self.kind = {}
        self._spellings = defaultdict(Counter)

    @property
    def files(self):
        return len(self.tags)

    def add(self, tags, file=None):
        file_id = len(self.tags)
        lowered = tuple(t.lower() for t in tags or [])
        self.tags.append(lowered)
        self.entries.append(file)
        for tag in tags or []:
            for word, kind in words_of(tag):
                if '"' in word:  # the query syntax has no way to write a quote
                    continue
                key = word.lower()
                self.files_by_word[key].add(file_id)
                self.kind.setdefault(key, kind)
                self._spellings[key][word] += 1

    def name(self, key):
        return self._spellings[key].most_common(1)[0][0]

    def label(self, key):
        name = self.name(key)
        kind = self.kind[key]
        if kind == "chara":
            return f"{name[len(CHARACTER_PREFIX):]}   [chara]"
        if kind == "tag":
            return f"{name}   [tag]"
        return name

    def count(self, key):
        return len(self.files_by_word[key])

    def suggest(self, text, exclude):
        text = text.lower()

        def bare(k):
            return k[len(CHARACTER_PREFIX):] if self.kind[k] == "chara" else k

        keys = [k for k in self.files_by_word if k not in exclude and text in k]
        keys.sort(key=lambda k: (bare(k) != text and k != text,
                                 not (bare(k).startswith(text) or k.startswith(text)),
                                 -self.count(k), k))
        return keys[:MAX_SUGGESTIONS]

    def _matching(self, terms):
        terms = [t.lower() for t in terms]
        for file_id, tags in enumerate(self.tags):
            if all(any(term in tag for tag in tags) for term in terms):
                yield file_id

    def matches(self, terms):
        return sum(1 for _ in self._matching(terms))

    def search(self, terms):
        """The Files matching terms, newest first; files added without one are left out."""
        found = [self.entries[i] for i in self._matching(terms) if self.entries[i] is not None]
        found.sort(key=lambda f: f.mtime or 0, reverse=True)
        return found


def query_text(terms):
    parts = []
    for term in terms:
        parts.append(f'tag:"{term}"' if any(c in term for c in QUERY_SPACES) else f"tag:{term}")
    return " ".join(parts)
