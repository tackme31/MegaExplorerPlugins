# CLAUDE.md

**Talk to the user in Japanese** — every reply, question and summary. Code, code comments, commit
messages and the plugins' READMEs stay in English.

**Change no code until the user explicitly asks for it to be implemented.** A question ("can
we…?"), a report of a problem, or agreement with an analysis asks for an answer: answer, propose,
and wait. Ask decisions with AskUserQuestion, with a recommended option first.

## What this repository is

Plugins for **MEGA Explorer** (https://github.com/tackme31/MegaExplorer), a Windows desktop client
for MEGA cloud storage. One folder per plugin, each a complete plugin with `plugin.json` at its top
and its own README (features, installation, building) and LICENSE. `README.md` here lists them.

| Folder | Plugin | Language |
| --- | --- | --- |
| `dirstat_plugin/` | MegaDirStat: size tree + treemap of a folder, in its own window. Read-only. | C++20 / Qt 6 Widgets |
| `wdtagger_plugin/` | WD Tagger: tags images/videos with a WD14 model on the GPU, as MEGA tags | Python / uv |
| `wdtagquerybuilder_plugin/` | WD Tag Query Builder: builds a `tag:` query over WD Tagger's tags, with suggestions and a match count. Read-only. | Python / uv |

Branch `main` only, pushed to `origin` (GitHub); pushing it is fine. Releases are zips of one
plugin folder, published as GitHub releases by `/release` (`.claude/skills/release/`).

## The plugin API

The contract is MEGA Explorer's `PLUGINS.md`:
https://github.com/tackme31/MegaExplorer/blob/develop/PLUGINS.md — read the relevant section
before using a method, and don't assume anything it does not say. In short: the app starts the
plugin's `run.command` per click, speaks JSON-RPC 2.0 over stdin/stdout (one message per line),
sends `initialize` → `command.execute` → `shutdown`, and the plugin calls `items.*` / `ui.*`
methods back. Every method needs the permission declared in `plugin.json`. stderr goes to the
app's log.

When a plugin needs something the API lacks, that is a change to MEGA Explorer, not a workaround
here: say so and propose it.

The Python plugins' `megaexplorer_plugin.py` is a copy of the helper in MEGA Explorer's sample
plugin (`plugin_sample/megaexplorer_plugin.py` in that repository). Don't edit a copy on its own;
changes go to the original first, then get copied into every Python plugin here.

## Running a plugin in the app

| MEGA Explorer build | Plugins folder |
| --- | --- |
| Debug (`dev` profile, signed in to a **test account**) | `%LOCALAPPDATA%\MegaExplorer\MegaExplorer-dev\plugins\` |
| Release (the user's **production** account) | `%LOCALAPPDATA%\MegaExplorer\MegaExplorer\plugins\` |

- **Development uses the dev profile**, with the plugin folder linked in by a directory junction
  (`mklink /J ...\MegaExplorer-dev\plugins\<name> <plugin folder>`); every plugin here is linked that
  way. Plugins are discovered at app start: after changing `plugin.json`, the app must be
  restarted. A program change applies on the next click.
- **The production folder holds copies**, not junctions, so a rebuild here never breaks the
  user's real setup. Install or refresh there only when asked.
- The user runs and restarts MEGA Explorer and builds its Release version. Driving its UI
  (clicks, keystrokes) needs the user's permission each time.
- **Screenshots: only the plugin's own window**, captured with `PrintWindow`
  (`PW_CLIENTONLY | PW_RENDERFULLCONTENT`). Never grab a screen region: other windows on the
  user's desktop end up in it.
- **Never load-test MEGA.** Try things on small test folders (tens of items). No measuring API
  limits by pushing hundreds or thousands of items; no prefetching or parallel requests added
  for speed unless real use runs into a limit. Reads through `items.get` / `children` /
  `descendants` come from the app's memory and don't reach MEGA, but `fetchPreview`, `fetchFile`,
  `items.update` and transfers do.

## dirstat_plugin (C++ / Qt)

Windows, MSVC (VS 2022), Qt 6.8+ for MSVC (the preset points at `C:/Qt/6.11.1/msvc2022_64`).
Always call CMake by its full path: the `cmake` on `PATH` is an older copy that cannot drive this
MSVC.

```
C:/Qt/Tools/CMake_64/bin/cmake.exe --preset msvc
C:/Qt/Tools/CMake_64/bin/cmake.exe --build --preset debug
C:/Qt/Tools/CMake_64/bin/ctest.exe --preset debug
pwsh scripts/deploy.ps1        # Release build + install exe and Qt DLLs into bin/
```

- `plugin.json` starts `bin/MegaDirStatPlugin.exe`, so the app runs what `deploy.ps1` last
  installed, not the Debug build. `bin/` and `build/` are gitignored.
- Builds at `/W4`; fix any warning of ours before calling a task done.
- `ctest` includes `tests/test_protocol.py`, which drives the exe over stdio like the app does
  (offscreen, no window). The plugin's own log categories are `dirstat.*`.
- The command's run stays open while the window is: `command.execute` is answered on window close,
  so the app greys the plugin's menu rows meanwhile. That is by design.
- The version lives only in `plugin.json`.
- `src/core` and the tree/treemap UI came from the separate MegaDirStat project; it is a separate
  project, so the two are not kept in sync.

## wdtagger_plugin (Python / uv)

```
uv sync
uv run python -m unittest
```

- Needs an NVIDIA GPU with CUDA 12 + cuDNN 9; `onnxruntime-gpu` is pinned to 1.23.2 because 1.24+
  is built for CUDA 13. Without CUDA it stops with an error; it never falls back to the CPU.
- Line endings are mixed (some files CRLF, most LF) and nothing normalises them: keep each file's
  own endings when editing it.
- `docs/SPEC.md` (Japanese) holds the design decisions and measurements. Read it before changing
  behaviour, and record a new decision there.

## wdtagquerybuilder_plugin (Python / uv)

```
uv sync
uv run python -m unittest
```

- No dependencies beyond Python; the window is tkinter. `tagquery.py` is the testable part (index,
  suggestions, match count, query text), `main.py` the window and the counting thread.
- The match count must follow MEGA Explorer's search rule exactly; `docs/SPEC.md` (Japanese) says
  which rule and why each deviation was closed. Read it before changing behaviour.

## Writing docs and commits

- Docs and READMEs must not contain anything specific to this machine or the user's accounts:
  local paths beyond tool defaults, folder or account names, plans, usage figures.
- One commit per working step, message in English with a body explaining why. Stage files by
  name. Check `git diff --stat` after rewriting a file from a script: a whole-file diff means its
  line endings or encoding changed too.
