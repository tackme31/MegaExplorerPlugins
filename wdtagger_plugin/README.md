# WD Tagger for MEGA Explorer

A MEGA Explorer plugin that tags images and videos in MEGA with what is in them, using the WD14
tagger model [`SmilingWolf/wd-eva02-large-tagger-v3`](https://huggingface.co/SmilingWolf/wd-eva02-large-tagger-v3).
The tags are stored as MEGA tags, so they can be searched with `tag:…` in MEGA Explorer.

## Usage

Right-click files or a folder → **WD Tagger**:

| Command | Does |
| --- | --- |
| **Tag selected** / **Tag all in folder** | Tags the files that have no tags from this plugin yet |
| **Retag selected** / **Retag all in folder** | Tags them again, replacing this plugin's tags |

- The model looks at the preview MEGA keeps for each file, so nothing is downloaded in full; a
  file without a preview is skipped.
- Each file gets up to three tags: `wd:` (general tags), `rating:` and `chara:` (characters).
  Tags starting with those prefixes are treated as the plugin's; your other tags are left alone.
- **Tagging changes your account and cannot be undone.** Try it on a small folder first.

## Requirements

- An **NVIDIA GPU with CUDA 12 and cuDNN 9**. There is no CPU fallback.
- [uv](https://docs.astral.sh/uv/) on `PATH`.
- About 1.2 GB of disk for the model, downloaded from Hugging Face on the first run.

## Installation

1. Unpack the release zip into a folder of its own in MEGA Explorer's plugins folder, so that
   `plugin.json` sits directly in it:
   `%LOCALAPPDATA%\MegaExplorer\MegaExplorer\plugins\wdtagger\plugin.json`
2. **Run `uv sync` once in that folder.** Left to the first run, the download can exceed MEGA
   Explorer's start-up limit for a plugin.
3. Restart MEGA Explorer.

## Settings

Optional `config.json` next to `plugin.json`; omitted keys keep their defaults.

```json
{
  "repo_id": "SmilingWolf/wd-eva02-large-tagger-v3",
  "thresh_general": 0.30,
  "thresh_character": 0.50,
  "thresh_rating": 0.40,
  "max_general_bytes": 2000
}
```

`thresh_*` are the minimum scores for a tag to be kept; `max_general_bytes` caps the `wd:` tag.

## Development

```
uv sync
uv run python -m unittest
```

`docs/SPEC.md` (Japanese) records the design decisions and measurements. `megaexplorer_plugin.py`
is a copy of the helper in MEGA Explorer's sample plugin.

## License

MIT — see [LICENSE](LICENSE). The model comes under its own license; see its model page.
