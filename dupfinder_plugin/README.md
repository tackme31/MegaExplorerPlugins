# Duplicate Finder for MEGA Explorer

A MEGA Explorer plugin that finds the files with the same content under a folder, groups them, and
shows how much space the extra copies waste. It compares the checksum MEGA keeps with each file, so
nothing is downloaded and even the whole Cloud Drive is checked in seconds. Read-only.

## Usage

Right-click a folder → **Duplicate Finder** → **Find duplicates...** The sets of duplicates are
listed in a window of its own, the most wasteful first. **Go to file** (or double-click) shows a
copy in MEGA Explorer, where you decide what to keep.

- **A match is near-certain, not proof**: for files above 8 KB the checksum covers a sample of the
  content, not every byte. Check the files before deleting one if that matters.
- Empty files, and files uploaded without a checksum by some older tools, are not compared.

## Requirements

- MEGA Explorer with plugin API version 1 and the `crc` item field.
- [uv](https://docs.astral.sh/uv/) on `PATH`. It fetches Python 3.12 on first use if needed.

## Installation

Copy this folder into MEGA Explorer's `plugins` folder and restart the app.

## Development

```
uv run python -m unittest
```

`duplicates.py` holds the grouping the tests cover; `main.py` the window. `megaexplorer_plugin.py`
is a copy of the helper in MEGA Explorer's sample plugin: change the original, then copy it here.

## License

MIT — see [LICENSE](LICENSE).
