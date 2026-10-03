# WD Tagger for MEGA Explorer

A MEGA Explorer plugin that tags images and videos in MEGA with what is in them, using the WD14
tagger model [`SmilingWolf/wd-eva02-large-tagger-v3`](https://huggingface.co/SmilingWolf/wd-eva02-large-tagger-v3).
The tags are stored as MEGA node tags, so MEGA Explorer's search (`tag:…`) and other MEGA clients
see them too.

## Features

Four commands, in the **WD Tagger** submenu of the right-click menu:

| Command | On | Does |
| --- | --- | --- |
| **Tag selected** | files | Tags the selected files that have no `wd:` tag yet |
| **Tag all in folder** | folders | The same for every file below the folder, at any depth |
| **Retag selected** | files | Tags the selected files again, replacing the plugin's previous tags |
| **Retag all in folder** | folders | The same for every file below the folder |

- **What gets tagged.** Images (`png jpg jpeg webp bmp`) and videos (`mp4 avi mkv webm mov wmv
  flv m4v gif`). The model looks at the preview MEGA keeps for each file — for a video, its
  representative frame — so nothing is downloaded in full. A file without a preview is skipped.
- **The tags.** At most three per item, leaving the rest of MEGA's 10-tag limit to you:
  - `wd:` — every general tag above the threshold, space-separated in one tag,
    e.g. `wd:1girl long_hair smile`
  - `rating:` — one of `general`, `sensitive`, `questionable`, `explicit`
  - `chara:` — the recognised characters, each prefixed, in one tag,
    e.g. `chara:hatsune_miku chara:mari_(blue_archive)`

  Tags you added yourself are left alone. Any tag starting with `wd:`, `rating:` or `chara:` is
  treated as the plugin's.
- **Search.** MEGA's tag search matches parts of a tag, so `tag:long_hair` or
  `tag:chara:hatsune_miku` in MEGA Explorer's search box finds them.
- **Progress and results.** A progress dialog with Cancel; when the run ends it turns into a
  summary listing the files that failed or had no preview.
- **Retag asks first**, naming the file or the number of files.
- **One run at a time**, also across several MEGA Explorer windows, so two runs never overwrite
  each other's tags.

Tagging changes the items in your account and there is no undo. Try it on a small folder first.

## Requirements

- An **NVIDIA GPU with CUDA 12 and cuDNN 9**. The plugin does not fall back to the CPU; without
  CUDA it stops with a message saying what it found.
- [**uv**](https://docs.astral.sh/uv/) on `PATH`. It provides Python and the dependencies.
- About **1.2 GB** of disk space for the model, downloaded from Hugging Face on the first run into
  the Hugging Face cache (`~/.cache/huggingface`).

## Installation

1. Download the plugin's zip from the Releases page and unpack it into a folder of its own inside
   MEGA Explorer's plugins folder, so that `plugin.json` sits directly in that folder:
   ```
   %LOCALAPPDATA%\MegaExplorer\MegaExplorer\plugins\wdtagger\plugin.json
   ```
2. **Run `uv sync` once in that folder.** It fetches Python and the dependencies (several hundred
   MB). Left to the first run instead, this counts against MEGA Explorer's five-minute start-up
   limit for a plugin, and on a slow connection the run is stopped before it begins.
3. Restart MEGA Explorer. **Settings › Plugins** lists it once it has loaded.

## Settings

Optional: a `config.json` next to `plugin.json`. Any key left out keeps its default.

```json
{
  "repo_id": "SmilingWolf/wd-eva02-large-tagger-v3",
  "thresh_general": 0.30,
  "thresh_character": 0.50,
  "thresh_rating": 0.40,
  "max_general_bytes": 2000
}
```

| Key | Meaning |
| --- | --- |
| `repo_id` | The Hugging Face model to use (a WD14 tagger with `model.onnx` and `selected_tags.csv`) |
| `thresh_general` / `thresh_character` / `thresh_rating` | Minimum score for a tag to be kept |
| `max_general_bytes` | Size cap of the `wd:` tag; the lowest-scoring tags are dropped beyond it |

Whatever the settings, the plugin keeps all of an item's tags within MEGA's limits (10 tags,
3000 bytes in total).

## Development

```
uv sync
uv run python -m unittest
```

While developing, link this folder into the plugins folder of MEGA Explorer's Debug build (the
`dev` profile) instead of copying it; a change to `main.py` then applies on the next run, a change
to `plugin.json` after restarting the app:

```
mklink /J "%LOCALAPPDATA%\MegaExplorer\MegaExplorer-dev\plugins\wdtagger" <this folder>
```

`megaexplorer_plugin.py` is a copy of the Python helper that ships with MEGA Explorer's sample
plugin. `docs/SPEC.md` (in Japanese) records the design decisions and the measurements behind them.

## License

MIT (see `LICENSE`). The model is downloaded from Hugging Face and comes under its own license;
see its model page.
