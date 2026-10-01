"""WD Tagger plugin for MegaExplorer."""

import onnxruntime as ort

from megaexplorer_plugin import Plugin

plugin = Plugin()


@plugin.command("check-env")
def check_env(ctx):
    providers = ort.get_available_providers()
    gpu = "CUDA" if "CUDAExecutionProvider" in providers else "CPU only"
    return f"onnxruntime {ort.__version__} ({gpu}), {len(ctx.items)} item(s) selected"


plugin.run()
