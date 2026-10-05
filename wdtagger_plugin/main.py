"""WD Tagger plugin for MegaExplorer (docs/SPEC.md)."""

import sys
import time
from pathlib import Path

import onnxruntime as ort

import model
from megaexplorer_plugin import CommandError, NoPreview, Plugin, RpcError
from single_run import one_at_a_time
from tags import build_tags, has_been_tagged, is_plugin_tag, is_taggable, load_config

plugin = Plugin()
CONFIG_PATH = Path(__file__).with_name("config.json")


NO_FILES = "Nothing to tag: no images or videos selected"
NO_FILES_IN_FOLDER = "Nothing to tag: no images or videos in this folder"


@plugin.command("tag-items")
@one_at_a_time
def tag_items(ctx):
    files = _selected_files(ctx)
    return _tag(ctx, files, retag=False) if files else NO_FILES


@plugin.command("tag-folder")
@one_at_a_time
def tag_folder(ctx):
    files = _files_in_folders(ctx)
    return _tag(ctx, files, retag=False) if files else NO_FILES_IN_FOLDER


@plugin.command("retag-items")
@one_at_a_time
def retag_items(ctx):
    files = _selected_files(ctx)
    if not files:
        return NO_FILES
    return _tag(ctx, files, retag=True) if _confirm_retag(ctx, files) else None


@plugin.command("retag-folder")
@one_at_a_time
def retag_folder(ctx):
    files = _files_in_folders(ctx)
    if not files:
        return NO_FILES_IN_FOLDER
    return _tag(ctx, files, retag=True) if _confirm_retag(ctx, files) else None


def _confirm_retag(ctx, files):
    """Retag throws away the plugin's current tags, so ask first; Cancel ends the
    command without a toast."""
    what = f'"{files[0].name}"' if len(files) == 1 else f"{len(files)} files"
    return ctx.confirm(
        f"Replace the wd:, rating: and chara: tags on {what} with new results? "
        "Tags you added yourself are kept.",
        title="Retag", ok_label="Retag", danger=True)


def _selected_files(ctx):
    return [item for item in ctx.items if item.is_file and is_taggable(item.name)]


def _files_in_folders(ctx):
    found = []
    for folder in ctx.items:
        if folder.is_folder:
            found.extend(_taggable_files_under(ctx, folder))
    return found


def _taggable_files_under(ctx, folder):
    found = []
    ctx.progress(message="Listing files…")
    for n, item in enumerate(ctx.descendants(folder, type="file"), 1):
        if n % 100 == 0:
            ctx.check_cancelled()
            ctx.progress(message=f"Listing files… {len(found)} found")
        if is_taggable(item.name):
            found.append(item)
    return found


def _tag(ctx, candidates, retag):
    """Without retag, items that already have a wd: tag are skipped; with it, the
    plugin's tags are replaced; the app sends MEGA only the tags that change."""
    config = load_config(CONFIG_PATH)
    todo = candidates if retag else [i for i in candidates if not has_been_tagged(i.tags)]
    already = len(candidates) - len(todo)
    if not todo:
        return f"Nothing to tag: {already} already tagged"

    started = time.perf_counter()
    tag_model = _load_model(ctx, config)
    timing = _Timing()
    timing.log(f"model load {time.perf_counter() - started:.2f}s, {len(todo)} to tag")
    tagged = unchanged = 0
    failed = []      # "<path>: <why>"
    no_preview = []  # paths
    timing.start()
    try:
        for n, item in enumerate(todo):
            ctx.check_cancelled()
            ctx.progress(n, len(todo), "Tagging…")
            t0 = time.perf_counter()
            try:
                preview = ctx.fetch_preview(item)
            except NoPreview:
                no_preview.append(item.path)
                continue
            except RpcError as error:
                failed.append(f"{item.path}: preview failed: {error}")
                continue
            t1 = time.perf_counter()
            try:
                probs = tag_model.predict(preview)
            finally:
                preview.unlink(missing_ok=True)
            t2 = time.perf_counter()
            tags = build_tags(probs, tag_model.names, tag_model.categories, config, item.tags)
            if not tags:
                failed.append(f"{item.path}: no room for tags next to {item.tags}")
                continue
            old = [t for t in item.tags if is_plugin_tag(t)]
            try:
                after = ctx.update(item, tags_add=tags, tags_remove=old)
            except RpcError as error:
                failed.append(f"{item.path}: update failed: {error}")
                continue
            # The app sends MEGA one request per tag that changes.
            writes = len(set(item.tags) ^ set(after.tags))
            timing.add(t1 - t0, t2 - t1, time.perf_counter() - t2, writes)
            if set(after.tags) == set(item.tags):
                unchanged += 1
            else:
                print(f"{item.name}: {tags}", file=sys.stderr)
                tagged += 1
        ctx.progress(len(todo), len(todo), "Tagging…")
    finally:
        timing.summary()

    parts = [f"{'Retagged' if retag else 'Tagged'} {tagged}"]
    if unchanged:
        parts.append(f"{unchanged} unchanged")
    if no_preview:
        parts.append(f"{len(no_preview)} without a preview")
    if already:
        parts.append(f"{already} already tagged")
    if failed:
        parts.append(f"{len(failed)} failed")
    lines = [", ".join(parts)]
    for heading, entries in (("Failed:", failed), ("Without a preview (skipped):", no_preview)):
        if entries:
            lines += ["", heading] + [f"  {entry}" for entry in entries]
    return "\n".join(lines)


class _Timing:
    """Average per-stage times on stderr (the app's log) every SUMMARY_EVERY items
    and at the end, to notice MEGA slowing down or throttling during a long run."""

    SUMMARY_EVERY = 50

    def __init__(self):
        self.count = self.writes = self.logged = 0
        self.fetch = self.predict = self.update = 0.0
        self.started = time.perf_counter()

    def start(self):
        self.started = time.perf_counter()

    @staticmethod
    def log(text):
        print(f"timing: {text}", file=sys.stderr)

    def add(self, fetch, predict, update, writes):
        self.count += 1
        self.writes += writes
        self.fetch += fetch
        self.predict += predict
        self.update += update
        if self.count % self.SUMMARY_EVERY == 0:
            self.summary()

    def summary(self):
        if self.count == self.logged:
            return
        self.logged = n = self.count
        elapsed = time.perf_counter() - self.started
        per_write = self.update / self.writes if self.writes else 0.0
        self.log(f"avg of {n}: fetch={self.fetch / n:.3f} predict={self.predict / n:.3f} "
                 f"update={self.update / n:.3f} ({self.writes / n:.1f} writes, "
                 f"{per_write:.3f}s/write), wall {elapsed:.1f}s = {elapsed / n:.3f}s/item")


def _load_model(ctx, config):
    def on_download(done_mb, total_mb):
        ctx.progress(done_mb, total_mb, "Downloading model (first run only)")

    model_path, tags_path = model.download(config.repo_id, on_download)
    ctx.progress(message="Loading model…")
    tag_model = model.TagModel(model_path, tags_path)
    if not tag_model.on_gpu:
        raise CommandError(
            "CUDA is not available, so the model cannot run on the GPU\n\n"
            f"onnxruntime {ort.__version__}, providers: {', '.join(ort.get_available_providers())}\n"
            "This plugin needs an NVIDIA GPU with CUDA 12 and cuDNN 9 "
            "(onnxruntime-gpu 1.24 and later need CUDA 13).")
    return tag_model


plugin.run()
