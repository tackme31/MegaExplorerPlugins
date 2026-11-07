"""Times the queries a search UI would run against the database main.py builds: an
exact-word AND search materialised into a temp table, its count, one page sorted by
mtime, the facets over the hits, and a similarity ranking over the inverted index.

The similarity weights follow similar.py's shape (IDF times a weight falling with the
word's position in its tag) but not its exact numbers: the cost, not the ranking, is
what is measured. Runnable on its own: python querybench.py [database]
"""

import math
import sys
import time

from store import DB_PATH
from tagsplit import CHARACTER, GENERAL, RATING

PAGE = 40
FACETS = 20
# The word's weight falls linearly from 1.0 at position 0 to 0.5 at POSITION_SPAN.
POSITION_SPAN = 50.0
POSITION_WEIGHT = f"(1.0 - 0.5 * MIN(position, {POSITION_SPAN}) / {POSITION_SPAN})"


def open_database(path):
    import sqlite3
    db = sqlite3.connect(path, isolation_level=None)
    db.execute("PRAGMA temp_store = MEMORY")
    db.execute("PRAGMA cache_size = -262144")
    db.execute("PRAGMA mmap_size = 2147483648")
    return db


def timed(function, *args):
    started = time.perf_counter()
    result = function(*args)
    return result, time.perf_counter() - started


# --- one-time preparation for similarity -------------------------------------------

def has_column(db, table, column):
    return any(row[1] == column for row in db.execute(f"PRAGMA table_info({table})"))


def prepare(db):
    """Adds tags.idf and item_norms when missing; returns seconds spent, or None."""
    if has_column(db, "tags", "idf") and db.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'item_norms'").fetchone():
        return None
    started = time.perf_counter()
    files = db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    db.execute("BEGIN")
    if not has_column(db, "tags", "idf"):
        db.execute("ALTER TABLE tags ADD COLUMN idf REAL NOT NULL DEFAULT 0")
    db.executemany("UPDATE tags SET idf = ? WHERE id = ?",
                   [(math.log(files / count) if count else 0.0, tag_id)
                    for tag_id, count in db.execute("SELECT id, item_count FROM tags")])
    db.execute("DROP TABLE IF EXISTS item_norms")
    db.execute("CREATE TABLE item_norms (item_id INTEGER PRIMARY KEY, norm REAL NOT NULL)")
    rows = db.execute(f"""
        SELECT it.item_id, SUM((t.idf * {POSITION_WEIGHT}) * (t.idf * {POSITION_WEIGHT}))
        FROM item_tags it JOIN tags t ON t.id = it.tag_id
        WHERE t.kind IN ({GENERAL}, {CHARACTER})
        GROUP BY it.item_id""").fetchall()
    db.executemany("INSERT INTO item_norms VALUES (?, ?)",
                   ((item_id, math.sqrt(sq)) for item_id, sq in rows if sq > 0))
    db.execute("COMMIT")
    return time.perf_counter() - started


# --- picking test words from the data ----------------------------------------------

def word_near(db, kind, share, files):
    """The word of kind whose file count is closest to share of all files."""
    return db.execute(
        "SELECT id, word, item_count FROM tags WHERE kind = ? AND item_count > 0 "
        "ORDER BY ABS(item_count - ?) LIMIT 1", (kind, share * files)).fetchone()


def top_word(db, kind):
    return db.execute("SELECT id, word, item_count FROM tags WHERE kind = ? "
                      "ORDER BY item_count DESC LIMIT 1", (kind,)).fetchone()


def typical_item(db):
    """A tagged file with the median number of words, to search similar files from."""
    counts = db.execute("SELECT item_id, COUNT(*) FROM item_tags GROUP BY item_id "
                        "ORDER BY 2 LIMIT 1 OFFSET (SELECT COUNT(DISTINCT item_id) / 2 "
                        "FROM item_tags)").fetchone()
    return counts


def label(word):
    return f"{word[1]}({word[2]:,})"


def build_cases(db):
    files = db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    top = top_word(db, GENERAL)
    ten = word_near(db, GENERAL, 0.10, files)
    one = word_near(db, GENERAL, 0.01, files)
    rare = word_near(db, GENERAL, 100 / files if files else 0, files)
    chara = top_word(db, CHARACTER)
    explicit = db.execute("SELECT id, word, item_count FROM tags WHERE kind = ? AND word = ?",
                          (RATING, "explicit")).fetchone()
    big = "i.size > 1048576 AND i.name LIKE '%.png'"
    cases = [
        ("all files", [], None),
        (f"{label(top)}", [top], None),
        (f"{label(ten)}", [ten], None),
        (f"{label(top)} {label(ten)}", [top, ten], None),
        (f"{label(one)} {label(chara)}" if chara else label(one),
         [one] + ([chara] if chara else []), None),
        (label(rare), [rare], None),
        (f"{label(top)} + .png > 1 MiB", [top], big),
    ]
    if explicit:
        cases.append((f"rating:{label(explicit)}", [explicit], None))
    return [c for c in cases if all(w is not None for w in c[1])]


# --- the search queries ------------------------------------------------------------

def materialise(db, words, condition):
    db.execute("DROP TABLE IF EXISTS temp.hits")
    db.execute("CREATE TEMP TABLE hits (item_id INTEGER PRIMARY KEY)")
    if words:
        match = " INTERSECT ".join("SELECT item_id FROM item_tags WHERE tag_id = ?" for _ in words)
        params = [w[0] for w in words]
    else:
        match = "SELECT id FROM items"
        params = []
    if condition:
        match = f"SELECT i.id FROM items i WHERE i.id IN ({match}) AND {condition}"
    db.execute(f"INSERT INTO hits {match}", params)


def count(db):
    return db.execute("SELECT COUNT(*) FROM hits").fetchone()[0]


def page(db):
    return db.execute("SELECT i.id, i.handle, i.name, i.size, i.mtime FROM hits "
                      "JOIN items i ON i.id = hits.item_id "
                      f"ORDER BY i.mtime DESC LIMIT {PAGE}").fetchall()


def facets(db, hits, files):
    # Few hits: look up each hit's words (CROSS JOIN pins hits as the outer loop).
    # Many hits: one pass over item_tags in tag_id order is cheaper. Measured crossover
    # is about a tenth of the files.
    join = "CROSS JOIN" if hits < files / 10 else "JOIN"
    rows = db.execute(f"SELECT it.tag_id, COUNT(*) AS n FROM hits "
                      f"{join} item_tags it ON it.item_id = hits.item_id "
                      "GROUP BY it.tag_id ORDER BY n DESC").fetchall()
    kinds = dict(db.execute("SELECT id, kind FROM tags").fetchall())
    best = {}
    for tag_id, n in rows:
        kind_rows = best.setdefault(kinds[tag_id], [])
        if len(kind_rows) < FACETS:
            kind_rows.append((tag_id, n))
    return best


def run_search(db, words, condition, files):
    steps = {}
    _, steps["hits"] = timed(materialise, db, words, condition)
    hits, steps["count"] = timed(count, db)
    _, steps["page"] = timed(page, db)
    _, steps["facets"] = timed(facets, db, hits, files)
    return hits, steps


# --- similarity ----------------------------------------------------------------------

def similar(db, item_id, restrict):
    """The PAGE files most like item_id; restrict limits candidates to temp.hits."""
    join = "JOIN hits h ON h.item_id = it.item_id" if restrict else ""
    return db.execute(f"""
        WITH q AS (
            SELECT it.tag_id, t.idf * {POSITION_WEIGHT} AS w
            FROM item_tags it JOIN tags t ON t.id = it.tag_id
            WHERE it.item_id = :item AND t.kind IN ({GENERAL}, {CHARACTER})),
        dots AS (
            SELECT it.item_id, SUM(q.w * t.idf * {POSITION_WEIGHT.replace('position', 'it.position')}) AS dot
            FROM q JOIN item_tags it ON it.tag_id = q.tag_id
            JOIN tags t ON t.id = it.tag_id
            {join}
            WHERE it.item_id != :item
            GROUP BY it.item_id)
        SELECT dots.item_id, dots.dot / n.norm AS score
        FROM dots JOIN item_norms n ON n.item_id = dots.item_id
        ORDER BY score DESC LIMIT {PAGE}""", {"item": item_id}).fetchall()


# --- the run -------------------------------------------------------------------------

def run(path, progress=lambda text: None):
    db = open_database(path)
    lines = []
    files = db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    rows = db.execute("SELECT COUNT(*) FROM item_tags").fetchone()[0]
    lines.append(f"{files:,} files, {rows:,} item-tag rows")

    progress("Preparing similarity weights (once per database)...")
    prepared = prepare(db)
    lines.append(f"Similarity prep: {prepared:.2f} s (stored in the database)" if prepared is not None
                 else "Similarity prep: already in the database")
    lines.append("")

    header = f"{'search':<44}{'hits':>9}{'hits':>8}{'count':>7}{'page':>7}{'facets':>8}{'total':>8}{'2nd':>8}"
    lines += ["Search (seconds; 1st run broken down, 2nd run total)", header, "-" * len(header)]
    cases = build_cases(db)
    for number, (name, words, condition) in enumerate(cases, 1):
        progress(f"Search {number}/{len(cases)}: {name}")
        hits, steps = run_search(db, words, condition, files)
        _, second = run_search(db, words, condition, files)
        lines.append(f"{name[:43]:<44}{hits:>9,}{steps['hits']:>8.2f}{steps['count']:>7.2f}"
                     f"{steps['page']:>7.2f}{steps['facets']:>8.2f}{sum(steps.values()):>8.2f}"
                     f"{sum(second.values()):>8.2f}")
    lines.append("")

    item = typical_item(db)
    if item:
        item_id, words = item
        ten = word_near(db, GENERAL, 0.10, files)
        lines.append(f"Similarity from item {item_id} ({words} words), top {PAGE}")
        progress("Similarity search...")
        _, first = timed(similar, db, item_id, False)
        _, again = timed(similar, db, item_id, False)
        lines.append(f"  whole index: {first:.2f} s, 2nd {again:.2f} s")
        progress("Similarity search within a search...")
        materialise(db, [ten], "i.size > 1048576")
        within = count(db)
        _, first = timed(similar, db, item_id, True)
        _, again = timed(similar, db, item_id, True)
        lines.append(f"  within {label(ten)} + > 1 MiB ({within:,} hits): "
                     f"{first:.2f} s, 2nd {again:.2f} s")
    db.close()
    return "\n".join(lines)


if __name__ == "__main__":
    print(run(sys.argv[1] if len(sys.argv) > 1 else DB_PATH, progress=lambda t: print(t, file=sys.stderr)))
