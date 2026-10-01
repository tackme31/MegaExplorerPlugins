"""WD Tagger plugin for MegaExplorer (docs/SPEC.md)."""

import sys
from pathlib import Path

import onnxruntime as ort

import model
from megaexplorer_plugin import CommandError, NoPreview, Plugin, RpcError
from tags import build_tags, has_been_tagged, is_taggable, load_config

plugin = Plugin()
CONFIG_PATH = Path(__file__).with_name("config.json")


@plugin.command("check-env")
def check_env(ctx):
    providers = ort.get_available_providers()
    gpu = "CUDA" if "CUDAExecutionProvider" in providers else "CPU only"
    return f"onnxruntime {ort.__version__} ({gpu}), {len(ctx.items)} item(s) selected"


@plugin.command("tag-items")
def tag_items(ctx):
    return _tag(ctx, [item for item in ctx.items if item.is_file])


@plugin.command("tag-folder")
def tag_folder(ctx):
    raise CommandError("Tagging a folder is not implemented yet")


def _tag(ctx, files):
    config = load_config(CONFIG_PATH)
    candidates = [item for item in files if is_taggable(item.name)]
    if not candidates:
        return "Nothing to tag: no images or videos selected"
    todo = [item for item in ctx.get_many(candidates) if not has_been_tagged(item.tags)]
    already = len(candidates) - len(todo)
    if not todo:
        return f"Nothing to tag: {already} already tagged"

    tag_model = _load_model(ctx, config)
    tagged = skipped = failed = 0
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
        try:
            ctx.update(item, tags_add=tags)
            print(f"{item.name}: {tags}", file=sys.stderr)
            tagged += 1
        except RpcError as error:
            print(f"{item.name}: update failed: {error}", file=sys.stderr)
            failed += 1
    ctx.progress(len(todo), len(todo), "Tagging…")

    parts = [f"Tagged {tagged}"]
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
