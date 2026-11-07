# WD Gallery for MEGA Explorer

A MEGA Explorer plugin that searches the drive's images and videos by
[WD Tagger](../wdtagger_plugin/README.md)'s tags, name, size, date and similarity, in a window of
thumbnails. Read-only.

## Usage

Right-click anything (a file, a folder or the empty space of a view) → **WD Gallery** → **Open
gallery...**. The window covers the whole drive the clicked item is in.

- **Search bar.** Type a condition and press Enter; every condition must match. Remove one with
  its ×, or Backspace in the empty box.
  - `long_hair` (or `long hair`): files carrying that tag, matched as a whole word, not a part of
    one. WD Tagger's words and your own tags both count. Suggestions with file counts appear as
    you type; ↑/↓ and Enter or Tab pick one. The ⊖ on a tag's chip turns it around: files
    *without* that tag (⊕ turns it back).
  - `chara:hatsune_miku`: files with that character, with suggestions.
  - `name:text`: the file name contains `text` (ignoring case).
  - `size:>1MB`, `size:<500KB` (B, KB, MB, GB).
  - `modified:>2025-01-01` (that day or later), `modified:<2025-01-01` (before it).
- **Rating** (left): tick one or more to show only those; the counts are for the current search.
- **Grid**: 60 files a page, newest first unless sorted otherwise. A video has a play mark.
- **Popup** (click a file): the preview, or the video playing; path, size, date, rating,
  characters and tags. ←/→ step through the results, Esc closes. Click a tag or character to add
  it to the search. **Find similar** adds a "similar to" condition: the results become the files
  whose WD Tagger tags are most like this file's, best first, still narrowed by the other
  conditions and ratings. Copies of the file (same size and content checksum) are left out.
  **Open in app** opens the file in MEGA Explorer's viewer; **Show in folder** shows it there.

## The index

The first time, the gallery reads every file of the drive from MEGA Explorer (from its memory,
not from MEGA) and keeps an index of them on disk, in
`%LOCALAPPDATA%\MegaExplorer-WDGallery\`, one file per drive. Later opens use that index at once.
It does not follow changes: files added, deleted or tagged since are seen after **Rebuild** (top
right), which reads the drive again; on a large drive that takes a minute or more.

Thumbnails, previews and videos are downloaded from MEGA, only for what is on screen.

## Requirements

- MEGA Explorer with `ui.open` (newer than 0.7.0) and `items.streamUrl`.
- Windows x64.

## Installation

Copy this folder, with its `bin/` built, into MEGA Explorer's `plugins` folder and restart the app.

## Development

```
npm ci
npm run typecheck
npm test           # the index and search, on Electron's own Node and SQLite
npm run pack       # bin/win-unpacked/, which plugin.json starts
```

`src/main/store.ts` is the index (building and searching, SQLite through `node:sqlite`),
run in a worker thread (`worker.ts`); `src/main/index.ts` talks to MEGA Explorer and serves
thumbnails and previews to the window; `src/renderer/` is the window.
