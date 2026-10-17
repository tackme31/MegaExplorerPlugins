# WD Tag Search for MEGA Explorer

A MEGA Explorer plugin that builds a `tag:` search query over the tags
[WD Tagger](../wdtagger_plugin/README.md) stores, with suggestions from the tags on your files and
a live count of the files it matches, then runs it in MEGA Explorer's search. Read-only.

## Usage

Right-click anywhere → **WD Tag Search** → **Open builder...** Type in the tag field and pick from
the suggestions, choose a rating if you like, and press **Search**.

| Key | Does |
| --- | --- |
| Up / Down, Enter | Pick a suggestion |
| Shift+Enter | Add the text as typed |
| Backspace (field empty) | Remove the last tag |

- **Tag your files with WD Tagger first.** Other tags are only offered whole, and the rating
  finds nothing without WD Tagger's `rating:` tags.
- The count can differ from the search's result: it covers the whole Cloud Drive (the search only
  the open folder and below), files only, and the tags as they were when the window opened.

## Requirements

- MEGA Explorer newer than 0.4.1 (for `ui.search`).
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

`tagquery.py` holds the tag index and query rules the tests cover; `main.py` the window.
`docs/SPEC.md` (Japanese) records the design decisions. `megaexplorer_plugin.py` is a copy of the
helper in MEGA Explorer's sample plugin.

## License

MIT — see [LICENSE](LICENSE).
