"""Ranks files by how alike their WD Tagger tags are: cosine similarity over the
words each file carries, every word weighted by its IDF and by where it sits in its
tag (WD Tagger writes the words best first).
"""

import math
import sys
from dataclasses import dataclass

GENERAL_PREFIX = "wd:"
CHARACTER_PREFIX = "chara:"

# Hundredths -> fraction; levels are kept as small ints because CPython shares those,
# so a level costs one pointer per word instead of a float object.
_FRACTION = [i / 100 for i in range(101)]


def terms_of(tags):
    """{word: level} for the words of WD Tagger's wd: and chara: tags, in stored order,
    first occurrence kept. level is the word's weight in hundredths, falling linearly
    from 100 for the first word of its tag to 50 for the last. chara: words keep their
    prefix so a character never matches a general word."""
    terms = {}
    for tag in tags or ():
        if tag.startswith(GENERAL_PREFIX):
            words = [w for w in tag[len(GENERAL_PREFIX):].split(" ") if w]
        elif tag.startswith(CHARACTER_PREFIX):
            words = [w for w in tag.split(" ")
                     if w.startswith(CHARACTER_PREFIX) and len(w) > len(CHARACTER_PREFIX)]
        else:
            continue
        last = len(words) - 1
        for i, word in enumerate(words):
            level = round(100 - 50 * i / last) if last else 100
            # Interned: the same few thousand words repeat across every file.
            terms.setdefault(sys.intern(word), level)
    return terms


def fingerprint(size, crc):
    """What two copies of one file share (MEGA's size + content checksum); None when
    the file has no checksum, so it is never taken for a copy."""
    if size is None or crc is None:
        return None
    return hash((size, crc))


@dataclass
class Match:
    handle: str
    name: str
    path: str
    score: float
    shared: tuple
    terms: int
    has_thumbnail: bool


class Ranking:
    """Every file sharing a word with the query, best first."""

    def __init__(self, index, order, query):
        self.index = index
        self.order = order
        self.query = query

    def __len__(self):
        return len(self.order)

    def without_copies(self, fp):
        """The ranking minus the files whose fingerprint is fp; itself when fp is None."""
        if fp is None:
            return self
        entries = self.index.entries
        return Ranking(self.index, [(s, i) for s, i in self.order if entries[i][5] != fp], self.query)

    def page(self, start, count):
        matches = []
        for score, i in self.order[start:start + count]:
            handle, name, path, terms, _levels, _fp, has_thumbnail = self.index.entries[i]
            shared = tuple(t for t in terms if t in self.query)
            matches.append(Match(handle, name, path, score, shared, len(terms), has_thumbnail))
        return matches


class SimilarityIndex:
    def __init__(self):
        self.entries = []
        self.df = {}
        self._w2 = None

    def __len__(self):
        return len(self.entries)

    def add(self, handle, name, path, tags, size=None, crc=None, has_thumbnail=False):
        """Indexes one file; a file without WD Tagger words is skipped. Returns
        whether it was indexed."""
        terms = terms_of(tags)
        if not terms:
            return False
        self.entries.append((handle, name, path, tuple(terms), tuple(terms.values()),
                             fingerprint(size, crc), bool(has_thumbnail)))
        df = self.df
        for t in terms:
            df[t] = df.get(t, 0) + 1
        self._w2 = None
        return True

    def weights(self):
        """Squared IDF of every word, smoothed so a word on every file still counts a little."""
        if self._w2 is None:
            n = len(self.entries)
            self._w2 = {t: (math.log((n + 1) / (d + 1)) + 1) ** 2 for t, d in self.df.items()}
        return self._w2

    def rank(self, query, exclude=None):
        """Every file sharing a word with query ({word: level}, from terms_of), best
        first; `exclude` is a handle left out (the query file itself)."""
        w2 = self.weights()
        f = _FRACTION
        q = {t: w2[t] * f[level] for t, level in query.items() if t in w2}
        qn = sum(w2[t] * f[level] ** 2 for t, level in query.items() if t in w2)
        order = []
        if qn:
            for i, (handle, _name, _path, terms, levels, _fp, _thumb) in enumerate(self.entries):
                if handle == exclude:
                    continue
                dot = 0.0
                norm = 0.0
                for t, level in zip(terms, levels):
                    p = f[level]
                    norm += w2[t] * p * p
                    qt = q.get(t)
                    if qt is not None:
                        dot += qt * p
                if dot:
                    order.append((dot / math.sqrt(norm * qn), i))
            # Ties keep listing order, so the result does not shuffle between runs.
            order.sort(key=lambda e: (-e[0], e[1]))
        return Ranking(self, order, q)
