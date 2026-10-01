"""WD Tagger plugin for MegaExplorer."""

import onnxruntime as ort

from megaexplorer_plugin import Plugin

plugin = Plugin()


@plugin.command("check-env")
def check_env(ctx):
    providers = ort.get_available_providers()
    gpu = "CUDA" if "CUDAExecutionProvider" in providers else "CPU only"
    return f"onnxruntime {ort.__version__} ({gpu}), {len(ctx.items)} item(s) selected"


@plugin.command("tag-items")
def tag_items(ctx):
    return f"tag-items: not implemented yet ({len(ctx.items)} file(s))"


@plugin.command("tag-folder")
def tag_folder(ctx):
    return f"tag-folder: not implemented yet ({len(ctx.items)} folder(s))"


plugin.run()
