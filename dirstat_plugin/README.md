# MegaDirStat for MEGA Explorer

A MEGA Explorer plugin that shows what takes up the space in a folder: a
size-sorted tree on top and a treemap below, in a window of its own.

## Features

- **Where to run it.** Right-click a folder → **MegaDirStat › Show folder sizes**. It is also on
  the right-click menu of a view's empty space (the folder on screen) and of a row in the side
  panel's folder tree or Quick access — which makes **Cloud Drive** itself reachable. Several
  selected folders are shown side by side.
- **Tree.** Every folder with its share of its parent, size, file count and newest modification
  time, largest first.
- **Treemap.** One cell per file, coloured by file type; files too small to draw are merged into
  one muted cell per folder. Click a cell to select it in the tree.
- **Focus.** Right-click → **Focus on “…”** narrows tree and treemap to one folder; the
  breadcrumb, **Up** (Alt+Up / Backspace) and **Show All** go back out.
- **Show in MEGA Explorer.** Right-click → **Show “…” in MEGA Explorer**, or double-click a file
  in the tree: the app's current tab opens the folder the item is in, with the item selected.
- **Reload** (F5) reads the folder again, keeping the current focus.

It reads only MEGA Explorer's in-memory copy of the account (`items.descendants`), so it never
contacts MEGA's servers and needs no login of its own. It changes nothing: the only permission it
declares is `items.read`.

While the window is open the plugin counts as running, so its menu rows are greyed out; close the
window to run it on another folder. Closing MEGA Explorer, or signing out, closes the window too.

## Installation

Download the plugin's zip from the Releases page and unpack it into a folder of its own inside
MEGA Explorer's plugins folder, so that `plugin.json` sits directly in that folder:

```
%LOCALAPPDATA%\MegaExplorer\MegaExplorer\plugins\dirstat\plugin.json
%LOCALAPPDATA%\MegaExplorer\MegaExplorer\plugins\dirstat\bin\MegaDirStatPlugin.exe
...
```

Then restart MEGA Explorer. **Settings › Plugins** lists it once it has loaded. Everything it
needs (Qt and the MSVC runtime) is in `bin\`; nothing else has to be installed.

## Building

Requirements: Windows, Visual Studio 2022 (MSVC), Qt 6.8 or later for MSVC (the preset points at
`C:/Qt/6.11.1/msvc2022_64`), and CMake 3.21 or later. No MEGA SDK or vcpkg is involved.

```
cmake --preset msvc
cmake --build --preset debug
ctest --preset debug
```

`ctest` runs the unit tests (tree building, size aggregation, treemap layout) and, when Python 3 is
found at configure time, `tests/test_protocol.py`: the plugin exe driven over stdin/stdout the way
MEGA Explorer drives it, without showing a window.

To produce a usable plugin folder:

```
pwsh scripts\deploy.ps1
```

This builds Release and installs the exe with the Qt DLLs it needs into `bin\`, which is what
`plugin.json` starts. The plugin folder is then complete: zip it for a release, or, while
developing, link it into the plugins folder of the Debug build (the `dev` profile) with a
junction instead of copying:

```
mklink /J "%LOCALAPPDATA%\MegaExplorer\MegaExplorer-dev\plugins\dirstat" <this folder>
```

Re-run `deploy.ps1` after a change; a change to `plugin.json` needs a restart of the app.

## License

MIT (see `LICENSE`). The tree, treemap and size model come from MegaDirStat by the same author.
