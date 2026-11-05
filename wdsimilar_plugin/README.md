# WD Similar for MEGA Explorer

A MEGA Explorer plugin that lists the images and videos whose
[WD Tagger](../wdtagger_plugin/README.md) tags are most like a chosen file's, with thumbnails. It
compares the tags MEGA Explorer already holds in memory; only the thumbnails on screen are
downloaded. Read-only.

## Usage

Right-click one image or video tagged by WD Tagger → **WD Similar** → **Find similar images**. A
window opens with the most similar files in the Cloud Drive (or the folders set in
[Settings](#settings)) as a grid of thumbnails, best
first, 20 at a time (**Load more** for the next 20). Hover over one for its name, folder and score;
double-click it to show it in MEGA Explorer. Right-click a tile → **Find similar images** to search
from that file instead, and keep going from what turns up.

The window stays open. To search for another file, select it in MEGA Explorer and press **Search
selected**: the drive's tags were read when the window opened, so this takes a second or two even
on a large drive. Files tagged or retagged since then are only seen after **Rebuild index**.

**Hide copies of this file** (on by default) leaves out files with the same size and content
checksum as the one searched for.

Similarity is the cosine of the files' WD Tagger words (`wd:` and `chara:`). Each word is weighted
by how rare it is across the drive, so sharing `umbrella` counts for more than sharing `1girl`, and
by where it sits in its tag: WD Tagger writes the most confident words first, so the first word
counts fully and the last half as much. Ratings and your own tags are not compared.

## Settings

By default the whole Cloud Drive is listed. To list only some folders, which on a large drive
saves the time and the app memory a full listing takes, put a `settings.json` next to
`plugin.json`:

```json
{"folders": ["/Photos", "/Illustrations/2024"]}
```

- Paths start at the Cloud Drive root and match folder names exactly, case included. A folder
  inside another listed one adds nothing.
- A path that is not found is skipped and named on the status line; if none is found, nothing is
  listed. A missing folder never widens the listing to the whole drive.
- Without the file, or with an empty list, the whole drive is listed.
- The file is read when the window opens and on **Rebuild index**. It is not in the release zip, so a new version unpacked over the
  folder keeps it.

## Requirements

- MEGA Explorer 0.7.0 or later (an older version lists the plugin, but its window cannot read
  the drive).
- [uv](https://docs.astral.sh/uv/) on `PATH`. It fetches Python 3.12 and Pillow on first use.

## Installation

Copy this folder into MEGA Explorer's `plugins` folder and restart the app.

## Development

```
uv run python -m unittest
```

`similar.py` holds the ranking the tests cover; `main.py` the window. `megaexplorer_plugin.py` is a
copy of the helper in MEGA Explorer's sample plugin: change the original, then copy it here.

## License

MIT — see [LICENSE](LICENSE).
