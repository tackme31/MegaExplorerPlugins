# MEGA Explorer plugins

Plugins for MEGA Explorer, one folder each. Every folder holds a complete plugin (`plugin.json` at
its top) with its own README covering features, installation and building.

| Plugin | Description |
| --- | --- |
| [MegaDirStat](dirstat_plugin/README.md) | Shows what takes up the space in a folder — or the whole Cloud Drive — as a size-sorted tree and a treemap, in a window of its own. Read-only. |
| [WD Tagger](wdtagger_plugin/README.md) | Tags images and videos with what is in them, using a WD14 tagger model on the GPU, and stores the result as MEGA tags you can search for. |
| [WD Tag Search](wdtagsearch_plugin/README.md) | Searches by WD Tagger's tags: builds a `tag:` query with suggestions from the tags on your files and a count of the files it matches, then runs it in MEGA Explorer's search. Read-only. |
| [Duplicate Finder](dupfinder_plugin/README.md) | Lists the files under a folder that have the same content, grouped, with the space the extra copies waste, using the checksum MEGA keeps with each file — nothing is downloaded. **Go to file** shows a copy in the app. Read-only. |

## License

Each plugin carries its own license: see the `LICENSE` file in its folder.
