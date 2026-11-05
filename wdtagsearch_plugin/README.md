# WD Tag Search for MEGA Explorer

A MEGA Explorer plugin that searches your files by the tags
[WD Tagger](../wdtagger_plugin/README.md) stores, with suggestions from the tags on your files and
a live count of the files it matches, and shows the matches as a grid of thumbnails, newest first.
The same query can also be run in MEGA Explorer's own search. Read-only.

## Usage

Right-click anywhere → **WD Tag Search** → **Open search...** Type in the tag field and pick from
the suggestions that drop down under it, choose a rating if you like, and press **Search**. The
matches appear below as thumbnails: double-click one to open it in MEGA Explorer, right-click to
show it in its folder. **Search in MEGA Explorer** runs the query in the app's current tab instead.

| Key | Does |
| --- | --- |
| Up / Down | Move through the suggestions (Down on an empty field lists the most used tags) |
| Enter, Tab, click | Add the highlighted suggestion |
| Shift+Enter | Add the text as typed |
| Enter (field empty) | Search |
| Esc | Close the suggestions |
| Backspace (field empty) | Remove the last tag |

- **Tag your files with WD Tagger first.** Other tags are only offered whole, and the rating
  finds nothing without WD Tagger's `rating:` tags.
- The search covers the whole Cloud Drive, files only, with the tags as they were when the window
  opened. **Search in MEGA Explorer** searches the open folder and below, so it can find fewer.

## Requirements

- MEGA Explorer with `items.fetchThumbnail` and `ui.open` (newer than 0.7.0).
- [uv](https://docs.astral.sh/uv/) on `PATH`.

## Installation

1. Unpack the release zip into a folder of its own in MEGA Explorer's plugins folder, so that
   `plugin.json` sits directly in it:
   `%LOCALAPPDATA%\MegaExplorer\MegaExplorer\plugins\wdtagsearch\plugin.json`
2. Run `uv sync` once in that folder.
3. Restart MEGA Explorer.

## Development

```
uv sync
uv run python -m unittest
```

`tagquery.py` holds the tag index, search and query rules the tests cover; `main.py` the window.
`docs/SPEC.md` (Japanese) records the design decisions. `megaexplorer_plugin.py` is a copy of the
helper in MEGA Explorer's sample plugin.

## License

MIT — see [LICENSE](LICENSE).
