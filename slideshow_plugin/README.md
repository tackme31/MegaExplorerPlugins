# Slideshow for MEGA Explorer

![](./img/screenshot.png)

A MEGA Explorer plugin that plays the images in a folder as a slideshow, in a window of its own,
with sorting, filtering and transitions. Images are streamed from MEGA as they are shown; nothing is
downloaded to disk.

## Usage

Right-click a folder → **Slideshow** → **This folder only** or **Including subfolders**.

| Key | Does |
| --- | --- |
| Space | Pause / play |
| ← / →, mouse wheel | Previous / next image |
| F, F11, double-click | Full screen (Esc leaves it) |
| + / − | Show each image longer / shorter |
| S | Settings |

- JPEG, PNG, WebP, GIF, AVIF and BMP are shown; HEIC, TIFF, RAW and PSD are not.
- The settings are saved in `settings.json` in the plugin's folder, so replacing the folder with
  a new version resets them.

## Requirements

- Windows 10 or 11, 64-bit.
- MEGA Explorer with `items.streamUrl` (an older version does not load the plugin).

## Installation

Unpack the release zip into a folder of its own in MEGA Explorer's plugins folder, so that
`plugin.json` sits directly in it (`...\plugins\slideshow\plugin.json`), and restart the app.
Everything it needs is in `bin\`.

## Building

Node.js 22 or later.

```
npm ci
npm run typecheck
npm run pack       # bin/win-unpacked/, which plugin.json starts
npm run package    # the same, then ../dist/Slideshow-<version>.zip
```

The version lives only in `plugin.json`. `scripts/stdio_probe.mjs` drives the plugin over stdio as
MEGA Explorer does.

## License

MIT — see [LICENSE](LICENSE).
