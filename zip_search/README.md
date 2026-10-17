# ZIP Search for MEGA Explorer

A MEGA Explorer plugin that lists the files inside every ZIP under a folder in one table, filtered
by file name or by the ZIP's tags. It saves a single file out of its ZIP without downloading the
whole archive, and edits the ZIP's tags.

**Only the parts that are needed are read.** A ZIP keeps an index of its contents at its end; the
plugin reads just that index from MEGA for each ZIP, usually in one small request, and to save a
file it reads only that file's bytes from inside the archive.

## Features

One command in the **ZIP Search** submenu of the right-click menu: **List files in ZIPs...** It
opens a window of its own.

- **What is searched** is every `.zip` file in the folder you right-clicked and everything below it,
  at any depth.
- **Other extensions**: the box at the top takes a comma-separated list (`zip, cbz, epub`); press
  **Search** or Enter to search again with it. It is disabled while a search runs, and every window
  starts with `zip`. Only archives in ZIP format can be read (`.cbz`, `.epub`, `.jar`, Office
  files, …); others such as `.rar` or `.7z` are counted as unreadable. Right-click the empty space of a folder for the folder you are in, or the Cloud
  Drive for the whole drive. Several selected folders are searched together.
- **The table** has one row per file: the ZIP it is in, its folder inside the ZIP, its name, its
  size, and the ZIP's MEGA tags. Folders inside a ZIP have no rows of their own.
- **ZIPs appear one by one** as each index is read, with a progress bar and a count, so you can
  start looking before all of them are done.
- **Filter by file name**: type into the box above the table. Matching ignores case; several words
  separated by spaces must all appear in the name. Esc clears the box.
- **Filter by ZIP tag**: the second box keeps the files of ZIPs whose tags match. Separate tags
  with commas; each one must appear in one of the ZIP's tags (part of a tag is enough, case is
  ignored). Both boxes can be used together.
- **Right-click a row → Download** saves that file to your Downloads folder (a name already taken
  gets ` (1)`, ` (2)`, … added). Select several rows to save them all, one after another. The
  status line under the table says where each one went.
- **Download progress** is shown at the bottom of the window while files are being saved: a bar,
  the percentage of a file larger than 1 MiB (fetched in 8 MiB pieces), and which file of how
  many. **Cancel** at the bottom right stops the file being saved, after the piece in flight, and
  drops the ones still waiting; nothing half-written is left behind.
- **Right-click a row → Show ZIP in MEGA Explorer** selects the ZIP the file is in, in the app's
  current tab.
- **Right-click a row → Edit tags...** opens a dialog with ten boxes, one per tag MEGA allows on
  an item, filled with the ZIP's current tags. **Submit** saves the changes to MEGA; empty boxes
  are ignored, and a tag cannot contain a comma. The table and the tag filter follow at once.
- **Use cache** (off by default) keeps each ZIP's index once it has been read, in `cache.json` in
  the plugin's folder. A later search takes a ZIP's files from there instead of reading MEGA, as
  long as the ZIP's modified time and size are unchanged; a changed ZIP is read again. The box is
  remembered between windows. **Clear cache** deletes the whole cache. The line under the count
  says how many archives came from the cache.
- **Names written by older Japanese tools** (Shift_JIS without the UTF-8 flag) are shown correctly.
- **ZIPs that cannot be read** (damaged, or not really ZIPs) are counted above the table; the reason
  for each is in MEGA Explorer's log.

Saving supports the usual compression methods (stored, Deflate, bzip2, LZMA). Encrypted files and
Deflate64 cannot be saved; the status line says so.

Closing the window ends the command. A file still being saved is not left half-written: its
`.part` file is removed.

## Requirements

- MEGA Explorer with plugin API version 1 and `items.readRange`.
- [uv](https://docs.astral.sh/uv/) on `PATH`. It fetches Python 3.12 on first use if needed. No
  other dependencies.

## Installation

Copy this folder into MEGA Explorer's `plugins` folder and restart the app.

## Development

```
uv run python -m unittest
```

| File | What it holds |
| --- | --- |
| `zipindex.py` | Reading a ZIP's index and one entry through byte-range reads, name decoding, the filter, the index cache. What the tests cover. |
| `main.py` | The window, the thread that reads the ZIPs, and the one that saves files. |
| `megaexplorer_plugin.py` | A copy of the helper in MEGA Explorer's sample plugin. Change the original, then copy it here. |

## License

MIT — see [LICENSE](LICENSE).
