"""WD Tagger plugin for MegaExplorer (docs/SPEC.md)."""

import sys
from pathlib import Path

import onnxruntime as ort

import model
from megaexplorer_plugin import CommandError, NoPreview, Plugin, RpcError
from tags import build_tags, has_been_tagged, is_plugin_tag, is_taggable, load_config

plugin = Plugin()
CONFIG_PATH = Path(__file__).with_name("config.json")


@plugin.command("check-env")
def check_env(ctx):
    providers = ort.get_available_providers()
    gpu = "CUDA" if "CUDAExecutionProvider" in providers else "CPU only"
    return f"onnxruntime {ort.__version__} ({gpu}), {len(ctx.items)} item(s) selected"


NO_FILES = "Nothing to tag: no images or videos selected"
NO_FILES_IN_FOLDER = "Nothing to tag: no images or videos in this folder"


@plugin.command("tag-items")
def tag_items(ctx):
    files = _selected_files(ctx)
    return _tag(ctx, files, retag=False) if files else NO_FILES


@plugin.command("tag-folder")
def tag_folder(ctx):
    files = _files_in_folders(ctx)
    return _tag(ctx, files, retag=False) if files else NO_FILES_IN_FOLDER


@plugin.command("retag-items")
def retag_items(ctx):
    files = _selected_files(ctx)
    return _tag(ctx, files, retag=True) if files else NO_FILES


@plugin.command("retag-folder")
def retag_folder(ctx):
    files = _files_in_folders(ctx)
    return _tag(ctx, files, retag=True) if files else NO_FILES_IN_FOLDER


def _selected_files(ctx):
    candidates = [item for item in ctx.items if item.is_file and is_taggable(item.name)]
    return ctx.get_many(candidates) if candidates else []


def _files_in_folders(ctx):
    found = []
    for folder in ctx.items:
        if folder.is_folder:
            found.extend(_taggable_files_under(ctx, folder))
    return found


def _taggable_files_under(ctx, folder):
    """Depth-first; children() already carries tags, so no items.get afterwards."""
    found = []
    pending = [folder]
    while pending:
        ctx.check_cancelled()
        ctx.progress(message=f"Listing files… {len(found)} found")
        for child in ctx.children(pending.pop()):
            if child.is_folder:
                pending.append(child)
            elif child.is_file and is_taggable(child.name):
                found.append(child)
    return found


def _tag(ctx, candidates, retag):
    """candidates must carry their current tags (from items.get or items.children).
    Without retag, items that already have a wd: tag are skipped; with it, the
    plugin's tags are replaced; the app sends MEGA only the tags that change."""
    config = load_config(CONFIG_PATH)
    todo = candidates if retag else [i for i in candidates if not has_been_tagged(i.tags)]
    already = len(candidates) - len(todo)
    if not todo:
        return f"Nothing to tag: {already} already tagged"

    tag_model = _load_model(ctx, config)
    tagged = unchanged = skipped = failed = 0
    for n, item in enumerate(todo):
        ctx.check_cancelled()
        ctx.progress(n, len(todo), "Tagging…")
        try:
            preview = ctx.fetch_preview(item)
        except NoPreview:
            skipped += 1
            continue
        except RpcError as error:
            print(f"{item.name}: preview failed: {error}", file=sys.stderr)
            failed += 1
            continue
        try:
            probs = tag_model.predict(preview)
        finally:
            preview.unlink(missing_ok=True)
        tags = build_tags(probs, tag_model.names, tag_model.categories, config, item.tags)
        if not tags:
            print(f"{item.name}: no room for tags next to {item.tags}", file=sys.stderr)
            failed += 1
            continue
        old = [t for t in item.tags if is_plugin_tag(t)]
        try:
            after = ctx.update(item, tags_add=tags, tags_remove=old)
        except RpcError as error:
            print(f"{item.name}: update failed: {error}", file=sys.stderr)
            failed += 1
            continue
        if set(after.tags) == set(item.tags):
            unchanged += 1
        else:
            print(f"{item.name}: {tags}", file=sys.stderr)
            tagged += 1
    ctx.progress(len(todo), len(todo), "Tagging…")

    parts = [f"{'Retagged' if retag else 'Tagged'} {tagged}"]
    if unchanged:
        parts.append(f"{unchanged} unchanged")
    if skipped:
        parts.append(f"{skipped} without a preview")
    if already:
        parts.append(f"{already} already tagged")
    if failed:
        parts.append(f"{failed} failed (see the log)")
    return ", ".join(parts)


def _load_model(ctx, config):
    def on_download(done_mb, total_mb):
        ctx.progress(done_mb, total_mb, "Downloading model (first run only)")

    model_path, tags_path = model.download(config.repo_id, on_download)
    ctx.progress(message="Loading model…")
    tag_model = model.TagModel(model_path, tags_path)
    if not tag_model.on_gpu:
        raise CommandError("CUDA is not available, so the model cannot run on the GPU")
    return tag_model


plugin.run()
