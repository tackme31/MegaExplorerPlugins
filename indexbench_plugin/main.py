"""Index Bench: times reading every file under the chosen folders through
items.descendants, splitting their tags into words (tagsplit.py) and storing them in an
SQLite database, then shows how long each step took. Read-only: the database is a
throwaway in the temp folder, rebuilt on every run.
"""

import os
import sqlite3
import sys
import time
from datetime import datetime

import querybench
from megaexplorer_plugin import CommandError, Plugin, format_duration
from store import DB_DIR, DB_PATH, LOG_PATH
from tagsplit import KIND_NAMES, split_tags

plugin = Plugin()

FIELDS = ["name", "size", "mtime", "tags", "hasThumbnail"]
BATCH = 1000

SCHEMA = """
CREATE TABLE items (
    id INTEGER PRIMARY KEY,
    handle TEXT NOT NULL,
    name TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime INTEGER NOT NULL,
    has_thumbnail INTEGER NOT NULL,
    path TEXT
);
CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    kind INTEGER NOT NULL,
    word TEXT NOT NULL,
    item_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE item_tags (
    item_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    position INTEGER NOT NULL
);
"""

# Built after the load: filling a table first and indexing it once is much faster than
# keeping the indexes up to date row by row.
INDEXES = """
CREATE UNIQUE INDEX items_handle ON items(handle);
CREATE UNIQUE INDEX tags_kind_word ON tags(kind, word);
CREATE INDEX item_tags_tag ON item_tags(tag_id, item_id);
CREATE INDEX item_tags_item ON item_tags(item_id);
"""

COUNT_TAGS = """
UPDATE tags SET item_count = counts.n
FROM (SELECT tag_id, COUNT(*) AS n FROM item_tags GROUP BY tag_id) AS counts
WHERE tags.id = counts.tag_id
"""


class Timer:
    def __init__(self):
        self.seconds = {}

    def add(self, step, started):
        self.seconds[step] = self.seconds.get(step, 0.0) + time.perf_counter() - started


def open_database():
    os.makedirs(DB_DIR, exist_ok=True)
    for suffix in ("", "-journal", "-wal", "-shm"):
        try:
            os.remove(DB_PATH + suffix)
        except FileNotFoundError:
            pass
    db = sqlite3.connect(DB_PATH, isolation_level=None)
    db.execute("PRAGMA journal_mode = OFF")
    db.execute("PRAGMA synchronous = OFF")
    db.execute("PRAGMA cache_size = -200000")
    db.executescript(SCHEMA)
    return db


def build(ctx, with_paths):
    fields = FIELDS + (["path"] if with_paths else [])
    timer = Timer()
    total_started = time.perf_counter()
    db = open_database()
    db.execute("BEGIN")

    tag_ids = {}
    items, item_tags = [], []
    listed = tagged = 0
    first_page = None

    def flush():
        started = time.perf_counter()
        db.executemany("INSERT INTO items VALUES (?, ?, ?, ?, ?, ?, ?)", items)
        db.executemany("INSERT INTO item_tags VALUES (?, ?, ?)", item_tags)
        timer.add("insert", started)
        items.clear()
        item_tags.clear()

    for folder in ctx.items:
        pages = iter(ctx.descendants(folder, type="file", fields=fields))
        while True:
            started = time.perf_counter()
            item = next(pages, None)
            timer.add("list", started)
            if item is None:
                break
            if first_page is None:
                first_page = time.perf_counter() - total_started

            started = time.perf_counter()
            listed += 1
            words = split_tags(item.tags)
            if words:
                tagged += 1
            for kind, word, position in words:
                key = (kind, word)
                tag_id = tag_ids.get(key)
                if tag_id is None:
                    tag_id = tag_ids[key] = len(tag_ids) + 1
                item_tags.append((listed, tag_id, position))
            items.append((listed, item.handle, item.name, item.size, item.mtime,
                          1 if item.has_thumbnail else 0, item.path))
            timer.add("split", started)

            if len(items) >= BATCH:
                flush()
                ctx.check_cancelled()
                ctx.update_progress(message=f"{listed:,} files read",
                                    detail=f"{ctx.elapsed_text()} elapsed")
    flush()
    list_done = time.perf_counter() - total_started

    ctx.update_progress(message=f"{listed:,} files read. Building the indexes...",
                        detail=f"{ctx.elapsed_text()} elapsed")
    started = time.perf_counter()
    db.executemany("INSERT INTO tags (id, kind, word) VALUES (?, ?, ?)",
                   ((tag_id, kind, word) for (kind, word), tag_id in tag_ids.items()))
    timer.add("insert", started)
    started = time.perf_counter()
    # Not executescript(): it commits the open transaction first.
    for statement in filter(str.strip, INDEXES.split(";")):
        db.execute(statement)
    timer.add("index", started)
    started = time.perf_counter()
    db.execute(COUNT_TAGS)
    timer.add("count", started)
    started = time.perf_counter()
    db.execute("COMMIT")
    timer.add("commit", started)

    rows = db.execute("SELECT COUNT(*) FROM item_tags").fetchone()[0]
    by_kind = dict(db.execute("SELECT kind, COUNT(*) FROM tags GROUP BY kind").fetchall())
    db.close()
    total = time.perf_counter() - total_started
    return report(ctx, with_paths, timer, total, list_done, first_page, listed, tagged, rows,
                  by_kind)


def report(ctx, with_paths, timer, total, list_done, first_page, listed, tagged, rows, by_kind):
    def secs(value):
        return f"{value:8.2f} s" if value is not None else "       -"

    size = sum(os.path.getsize(DB_PATH + s) for s in ("", "-journal")
               if os.path.exists(DB_PATH + s))
    folders = ", ".join(item.path or item.name for item in ctx.items)
    lines = [
        f"{datetime.now():%Y-%m-%d %H:%M:%S}  {folders}  ({'with' if with_paths else 'no'} paths)",
        "",
        f"Files              {listed:>12,}",
        f"  with tags        {tagged:>12,}",
        f"Item-tag rows      {rows:>12,}"
        + (f"  ({rows / tagged:.1f} per tagged file)" if tagged else ""),
        "Distinct words     " + ", ".join(f"{KIND_NAMES[k]} {n:,}" for k, n in sorted(by_kind.items())),
        f"Database size      {size / 1024 / 1024:12.1f} MB",
        "",
        f"Total              {secs(total)}  ({format_duration(total)})",
        f"  first page       {secs(first_page)}",
        f"  read + stored    {secs(list_done)}",
        f"    reading        {secs(timer.seconds.get('list', 0))}  (items.descendants, incl. JSON)",
        f"    splitting      {secs(timer.seconds.get('split', 0))}",
        f"    inserting      {secs(timer.seconds.get('insert', 0))}",
        f"  indexes          {secs(timer.seconds.get('index', 0))}",
        f"  tag counts       {secs(timer.seconds.get('count', 0))}",
        f"  commit           {secs(timer.seconds.get('commit', 0))}",
        "",
        f"Database: {DB_PATH}",
    ]
    publish(ctx, "\n".join(lines))


def publish(ctx, text):
    print(text, file=sys.stderr)
    with open(LOG_PATH, "a", encoding="utf-8") as log:
        log.write(text + "\n\n")
    ctx.show_result(text + f"\nAppended to: {LOG_PATH}", title="Index Bench")


@plugin.command("build")
def build_index(ctx):
    return build(ctx, with_paths=False)


@plugin.command("build-paths")
def build_index_with_paths(ctx):
    return build(ctx, with_paths=True)


@plugin.command("query")
def query_bench(ctx):
    if not os.path.exists(DB_PATH):
        raise CommandError("No database yet: run Build index first.")
    started = time.perf_counter()

    def progress(text):
        ctx.check_cancelled()
        ctx.update_progress(message=text, detail=f"{ctx.elapsed_text()} elapsed")

    text = querybench.run(DB_PATH, progress)
    publish(ctx, f"{datetime.now():%Y-%m-%d %H:%M:%S}  Query bench  "
                 f"({time.perf_counter() - started:.1f} s)\n\n{text}\n\nDatabase: {DB_PATH}")


if __name__ == "__main__":
    plugin.run()
