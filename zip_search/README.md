# ZIP Search for MEGA Explorer

A MEGA Explorer plugin that lists the files inside every ZIP under a folder, in one table you can
filter by file name, and saves a single file out of its ZIP without downloading the whole archive.

**Only the parts that are needed are read.** A ZIP keeps an index of its contents at its end; the
plugin reads just that index from MEGA for each ZIP, usually in one small request, and to save a
file it reads only that file's bytes from inside the archive.

## Features

One command in the **ZIP Search** submenu of the right-click menu: **List files in ZIPs...** It
opens a window of its own.

- **What is searched** is every `.zip` file in the folder you right-clicked and everything below it,
  at any depth. Right-click the empty space of a folder for the folder you are in, or the Cloud
  Drive for the whole drive. Several selected folders are searched together.
- **The table** has one row per file: the ZIP it is in, its folder inside the ZIP, its name and its
  size. Folders inside a ZIP have no rows of their own.
- **ZIPs appear one by one** as each index is read, with a progress bar and a count, so you can
  start looking before all of them are done.
- **Filter by file name**: type into the box above the table. Matching ignores case; several words
  separated by spaces must all appear in the name. Esc clears the box.
- **Right-click a row → Download** saves that file to your Downloads folder (a name already taken
  gets ` (1)`, ` (2)`, … added). Select several rows to save them all, one after another. The
  status line under the table says where each one went.
- **Right-click a row → Show ZIP in MEGA Explorer** selects the ZIP the file is in, in the app's
  current tab.
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
| `zipindex.py` | Reading a ZIP's index and one entry through byte-range reads, name decoding, the filter. What the tests cover. |
| `main.py` | The window, the thread that reads the ZIPs, and the one that saves files. |
| `megaexplorer_plugin.py` | A copy of the helper in MEGA Explorer's sample plugin. Change the original, then copy it here. |

## License

MIT — see [LICENSE](LICENSE).
