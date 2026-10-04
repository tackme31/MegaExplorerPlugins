# Duplicate Finder for MEGA Explorer

A MEGA Explorer plugin that finds the files with the same content under a folder, groups them into
sets, and shows how much space the extra copies take. Pick a copy and MEGA Explorer opens the folder
it is in, so you can decide there what to keep.

**It reads nothing from MEGA.** Every file in MEGA carries a checksum of its content, computed by
the client that uploaded it. The plugin compares those, with the file sizes, from MEGA Explorer's
own copy of the account, so even the whole Cloud Drive is checked in seconds without downloading a
byte. It changes nothing either: moving or deleting a copy is done in MEGA Explorer as usual.

## Features

One command in the **Duplicate Finder** submenu of the right-click menu: **Find duplicates...** It
opens a window of its own.

- **What is checked** is the folder you right-clicked and everything below it, at any depth.
  Right-click the empty space of a folder for the folder you are in, or the Cloud Drive for the
  whole drive. With several folders selected, they are checked together, so copies spread across
  them are found too. Files outside are not compared.
- **The total waste** at the top: how much would be freed by keeping one copy of every set.
- **Sets of duplicates**, the ones that waste the most first. Each set's row shows the number of
  copies, the file size and the space its extra copies take; under it, each copy's name and
  folder. A set whose copies go by different names says so (`IMG_0001.jpg (+1 other name)`).
- **Go to file** shows the selected copy, selected, in MEGA Explorer's current tab. Double-clicking
  a copy or pressing Enter does the same.
- **Expand all / Collapse all** for the sets.
- **What was not compared** is counted under the total: empty files, and files uploaded without a
  checksum (some older clients and tools leave it out).

**A match is near-certain, not proof.** For files above 8 KB the checksum covers a spread-out 8 KB
sample of the content, not every byte, and is compared together with the exact size. Two different
files that agree on both are extremely unlikely, but possible: check the files before deleting one
if that matters.

The list is what the account looked like when the window opened. Files moved or deleted since stay
in it until you run the command again.

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

| File | What it holds |
| --- | --- |
| `duplicates.py` | Grouping by size and checksum, and the text formatting. What the tests cover. |
| `main.py` | The window, and the thread that lists the files. |
| `megaexplorer_plugin.py` | A copy of the helper in MEGA Explorer's sample plugin. Change the original, then copy it here. |

## License

MIT — see [LICENSE](LICENSE).
