# Index Bench for MEGA Explorer

A MEGA Explorer plugin that measures how long it takes to build a tag index of a folder: it reads
every file below the folder through `items.descendants`, splits each file's tags into words (WD
Tagger packs many words into one `wd:` or `chara:` tag), stores them in an SQLite database, and
reports how long each step took. Read-only; nothing is sent to MEGA.

## Usage

Right-click a folder (or the empty space of a view, for the folder it shows) → **Index Bench** →

- **Build index**: reads `name`, `size`, `mtime`, `tags` and `hasThumbnail`.
- **Build index with paths**: the same plus `path`, which the app works out per item, to see what
  it costs.

The progress dialog shows the count read so far and has Cancel. At the end a report shows the
file, row and word counts, the database size, and the time split into reading (the app's answer
to `items.descendants`, JSON included), splitting, inserting, building the indexes, counting the
files per word and committing. The report is also appended to `results.log` next to the
database.

The database is `megaexplorer-indexbench\index.sqlite` in the temp folder. It is kept between
runs and replaced only by **Build index**; open it with any SQLite tool to try queries.

**Query bench** (any context menu) times, on the database already built, the queries a search
window would run: exact-word AND searches over words picked from the data (the most common one,
ones on about 10 % and 1 % of the files, a rare one, a character, a rating, and one combined with
a name and size filter), each with its count, a page of 40 sorted by date and the facets over
the hits; then a similarity search from a typical file, over everything and within a search.
The first run adds IDF weights and per-file norms to the database (`tags.idf`, `item_norms`),
timed separately. `uv run python querybench.py [database]` runs the same outside the app.

## Tables

| Table | Columns |
| --- | --- |
| `items` | `id`, `handle`, `name`, `size`, `mtime`, `has_thumbnail`, `path` (null without paths) |
| `tags` | `id`, `kind` (0 general, 1 character, 2 rating, 3 your own tag), `word` (lowercased), `item_count` |
| `item_tags` | `item_id`, `tag_id`, `position` (the word's place in its tag, from 0) |

## Requirements

- MEGA Explorer 0.7.0 or later.
- [uv](https://docs.astral.sh/uv/) on `PATH`.

## Installation

Copy this folder into MEGA Explorer's `plugins` folder and restart the app.

## Development

```
uv run python -m unittest
```

`tagsplit.py` is the tested part; `main.py` the listing, the database and the report; `querybench.py` the query timings.
