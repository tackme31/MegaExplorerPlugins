# WD Tag Query Builder for MEGA Explorer

A MEGA Explorer plugin that helps you write a `tag:` query for the search box over the tags
[WD Tagger](../wdtagger_plugin/README.md) stores. It suggests tags from the ones already on your
files, shows how many files the query matches as you build it, and copies the finished query to
the clipboard for you to paste into MEGA Explorer's search box.

**It is built for WD Tagger's tags.** It knows how WD Tagger stores them — several words packed
into one `wd:` or `chara:` tag, and a `rating:` tag — and splits and offers them accordingly, so tag
your files with WD Tagger first. Tags from anywhere else are only offered whole, as they are
stored, and the rating drop-down finds nothing without WD Tagger's `rating:` tags.

## Features

One command in the **WD Tag Query Builder** submenu of the right-click menu (on a file, a folder,
or the empty space of a folder): **Open builder...** It opens a window of its own.

- **Suggestions from your own tags.** When the window opens, the plugin reads the tags on every
  file in the Cloud Drive and suggests from those, with how many files carry each one. Nothing is
  suggested that would find nothing. WD Tagger's tags are split into words: `wd:1girl solo` offers
  `1girl` and `solo`, and `chara:hatsune_miku` is offered as `hatsune_miku [chara]`. Tags you added
  yourself are offered whole, marked `[tag]`.
- **Rating** is a drop-down: All, or one of `general`, `sensitive`, `questionable`, `explicit`, each
  with its file count. MEGA Explorer's search has no OR, so only one rating can be picked.
- **Live match count.** The number of files the query matches in the Cloud Drive, counted with
  the same rule as MEGA Explorer's search.
- **Copy** puts the query on the clipboard, e.g. `tag:1girl tag:solo tag:rating:general`. The
  query field is editable, so you can adjust it before copying.

Keys in the tag field:

| Key | Does |
| --- | --- |
| Up / Down | Move through the suggestions |
| Enter, Tab, double-click | Add the selected suggestion |
| Shift+Enter | Add the text as typed, ignoring the suggestions |
| Backspace (field empty) | Remove the last tag |

Read-only: the plugin only reads the tags (permission `items.read`) and never changes your
account. Reading them comes from MEGA Explorer's memory, so it causes no MEGA traffic.

### What to know about the count

MEGA Explorer's tag search matches **parts** of a tag, ignoring case, and needs every term to be
found in some tag of the item. So `tag:solo` also finds `solo_focus`, and `tag:girl` finds `1girl`.
The count includes those matches too, so it agrees with the search, with these differences:

- It counts the **whole Cloud Drive**. The search looks in the folder you have open and its
  subfolders, so pasting the query anywhere but the root can find fewer files.
- It counts **files only**. The search also lists folders that carry the tags.
- It is the count **when the window opened**. Tags added while it is open are not counted; open it
  again to recount.

## Requirements

- [**uv**](https://docs.astral.sh/uv/) on `PATH`. It provides Python; the plugin has no other
  dependencies (the window is tkinter, which comes with Python).
- **Files tagged by [WD Tagger](../wdtagger_plugin/README.md)** — the plugin is meant to be used
  together with it (see above).

## Installation

1. Download the plugin's zip from the Releases page and unpack it into a folder of its own inside
   MEGA Explorer's plugins folder, so that `plugin.json` sits directly in that folder:
   ```
   %LOCALAPPDATA%\MegaExplorer\MegaExplorer\plugins\wdtagquerybuilder\plugin.json
   ```
2. Run `uv sync` once in that folder, so that fetching Python does not happen during the first run.
3. Restart MEGA Explorer. **Settings › Plugins** lists it once it has loaded.

## Development

```
uv sync
uv run python -m unittest
```

`tagquery.py` holds the tag index and the query rules, tested by `test_tagquery.py`; `main.py` is
the window. While developing, link this folder into the plugins folder of MEGA Explorer's Debug
build (the `dev` profile) instead of copying it; a change to the Python files then applies on the
next run, a change to `plugin.json` after restarting the app:

```
mklink /J "%LOCALAPPDATA%\MegaExplorer\MegaExplorer-dev\plugins\wdtagquerybuilder" <this folder>
```

`megaexplorer_plugin.py` is a copy of the Python helper that ships with MEGA Explorer's sample
plugin. `docs/SPEC.md` (in Japanese) records the design decisions.

## License

MIT (see `LICENSE`).
