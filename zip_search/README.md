# ZIP Search for MEGA Explorer

A MEGA Explorer plugin that lists the files inside every ZIP under a folder, and saves one of them
without downloading the whole archive. Only each ZIP's index, and the bytes of the file you save,
are read from MEGA.

## Usage

Right-click a folder → **ZIP Search** → **List files in ZIPs...** Every ZIP below it is listed in a
window of its own, one row per file inside.

- Filter the rows by file name or by the ZIP's MEGA tags.
- Right-click a row to **Download** the file to your Downloads folder, show its ZIP in MEGA
  Explorer, or edit the ZIP's tags.
- Other ZIP-format extensions (`cbz`, `epub`, …) can be searched too; `.rar` and `.7z` cannot.
- **Use cache** keeps the ZIP indexes already read, so searching the same folders again does not
  read them from MEGA. Off by default. The cache (`cache.json` in the plugin's folder) is
  unencrypted and holds the names of the files inside your ZIPs.

Encrypted entries and Deflate64 cannot be saved.

## Requirements

- MEGA Explorer with plugin API version 1 and `items.readRange`.
- [uv](https://docs.astral.sh/uv/) on `PATH`. It fetches Python 3.12 on first use if needed.

## Installation

Copy this folder into MEGA Explorer's `plugins` folder and restart the app.

## Development

```
uv run python -m unittest
```

`zipindex.py` holds everything the tests cover (reading a ZIP over byte ranges, the filters, the
cache); `main.py` the window. `megaexplorer_plugin.py` is a copy of the helper in MEGA Explorer's
sample plugin: change the original, then copy it here.

## License

MIT — see [LICENSE](LICENSE).
