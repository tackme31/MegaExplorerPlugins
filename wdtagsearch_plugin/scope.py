"""Which folders the files are listed from: the "folders" of settings.json next to
this file, or the whole drive when it names none.
"""

import json
import os

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


class SettingsError(Exception):
    pass


def normalize(path):
    parts = [p for p in path.strip().replace("\\", "/").split("/") if p]
    return "/" + "/".join(parts)


def outermost(paths):
    """The paths with duplicates and those inside another one left out."""
    kept = []
    for path in sorted(set(paths)):
        if not any(q == "/" or path == q or path.startswith(q + "/") for q in kept):
            kept.append(path)
    return kept


def load_folders(path=SETTINGS_PATH):
    """The folder paths to list, outermost only; None for the whole drive."""
    try:
        with open(path, encoding="utf-8") as f:
            settings = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        raise SettingsError(f"Could not read settings.json: {e}")
    if not isinstance(settings, dict):
        raise SettingsError("settings.json must hold a JSON object")
    folders = settings.get("folders")
    if folders is None:
        return None
    if not isinstance(folders, list) or not all(isinstance(p, str) for p in folders):
        raise SettingsError('settings.json: "folders" must be a list of folder paths')
    paths = [normalize(p) for p in folders if p.strip()]
    return outermost(paths) if paths else None


def resolve(ctx, root, path):
    """Every folder at path under root; MEGA allows siblings with the same name."""
    current = [root]
    for name in [p for p in path.split("/") if p]:
        current = [child for folder in current
                   for child in ctx.children(folder, type="folder", fields=["name"])
                   if child.name == name]
        if not current:
            break
    return current


def folders_to_list(ctx, root, paths):
    """(folders to list, paths not found). paths: load_folders()'s result.

    A path that is not found is left out rather than widening the listing to the
    whole drive: a renamed folder must not silently bring back a full scan."""
    if paths is None:
        return [root], []
    folders, missing = [], []
    for path in paths:
        found = resolve(ctx, root, path)
        if found:
            folders.extend(found)
        else:
            missing.append(path)
    return folders, missing


def describe(paths, missing):
    """A sentence to append to the status line; empty for the whole drive."""
    if paths is None:
        return ""
    listed = len(paths) - len(missing)
    note = f" Listed from {listed} folder{'s' if listed != 1 else ''} in settings.json."
    if missing:
        note += f" Not found: {', '.join(missing)}."
    return note
