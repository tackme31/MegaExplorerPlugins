"""The tag index and query building, kept free of tkinter and the app connection.

WD Tagger packs several words into one MEGA tag ("wd:1girl solo ...",
"chara:a chara:b"), so suggestions are per word, while the match count runs the
app's own rule on the stored tags: every term must be a case-insensitive
substring of some tag on the file.
"""

from collections import Counter, defaultdict

MAX_SUGGESTIONS = 50
GENERAL_PREFIX = "wd:"
CHARACTER_PREFIX = "chara:"
RATING_PREFIX = "rating:"
RATINGS = ("general", "sensitive", "questionable", "explicit")
# What the app's query parser splits words at; a term holding one needs quotes.
QUERY_SPACES = (" ", "\t", "　")


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
        self.files_by_word = defaultdict(set)
        self.kind = {}
        self._spellings = defaultdict(Counter)

    @property
    def files(self):
        return len(self.tags)

    def add(self, tags):
        file_id = len(self.tags)
        lowered = tuple(t.lower() for t in tags or [])
        self.tags.append(lowered)
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

    def matches(self, terms):
        terms = [t.lower() for t in terms]
        hits = 0
        for tags in self.tags:
            if all(any(term in tag for tag in tags) for term in terms):
                hits += 1
        return hits


def query_text(terms):
    parts = []
    for term in terms:
        parts.append(f'tag:"{term}"' if any(c in term for c in QUERY_SPACES) else f"tag:{term}")
    return " ".join(parts)
