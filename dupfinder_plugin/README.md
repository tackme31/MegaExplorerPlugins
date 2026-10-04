# Duplicate Finder for MEGA Explorer

A MEGA Explorer plugin that lists the files under a folder that have the same content, grouped
into sets, so you can see where copies are and how much space they take. Read-only: it shows the
files, and leaving or removing them is up to you.

**It reads nothing from MEGA.** Every file in MEGA carries a checksum of its content, computed by
the client that uploaded it. The plugin compares those, with the file sizes, from MEGA Explorer's
own copy of the account, so even a large folder is checked in seconds without downloading a byte.

## Features

One command in the **Duplicate Finder** submenu of the right-click menu (on a folder, or the empty
space of a folder — Cloud Drive included): **Find duplicates...** It opens a window of its own.

- **Sets of duplicates**, the ones that waste the most space first. Each set shows how many copies
  there are, the file size, and how much would be freed by keeping only one; under it, the path of
  every copy.
- **Double-click a file** to show it, selected, in MEGA Explorer's current tab.
- **What was not compared** is counted in the status line: empty files, and files uploaded without
  a checksum (some older clients and tools leave it out).

**A match is near-certain, not proof.** For files above 8 KB the checksum covers a spread-out
sample of the content, not every byte. Two different files of exactly the same size that agree on
that sample are extremely unlikely, but possible; check the files before deleting one if that
matters.

## Requirements

- MEGA Explorer with plugin API version 1 and the `crc` item field.
- [uv](https://docs.astral.sh/uv/) on `PATH`. It fetches Python 3.12 on first use if needed. No
  other dependencies.

## Installation

Copy this folder into MEGA Explorer's `plugins` folder and restart the app.

## Development

```
uv run python -m unittest
```

`duplicates.py` is the grouping and is what the tests cover; `main.py` is the window and the
listing thread. `megaexplorer_plugin.py` is a copy of the helper in MEGA Explorer's sample plugin.

## License

MIT — see [LICENSE](LICENSE).
