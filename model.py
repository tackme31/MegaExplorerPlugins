"""The WD14 model: download, load, preprocess, predict."""

from __future__ import annotations

import csv
import threading
from pathlib import Path

import numpy as np
import onnxruntime as ort
from huggingface_hub import constants, get_hf_file_metadata, hf_hub_url, try_to_load_from_cache
from huggingface_hub import hf_hub_download
from PIL import Image

MODEL_FILE = "model.onnx"
TAGS_FILE = "selected_tags.csv"


def download(repo_id, on_progress):
    """Paths of the model and its tag list, fetching what the HF cache lacks.

    on_progress(done_mb, total_mb) is called about once a second while
    model.onnx downloads; total_mb is None when the size is unknown.
    """
    paths = {}
    for filename in (TAGS_FILE, MODEL_FILE):
        cached = try_to_load_from_cache(repo_id, filename)
        if isinstance(cached, str):
            paths[filename] = cached
            continue
        paths[filename] = _download_with_progress(repo_id, filename, on_progress)
    return Path(paths[MODEL_FILE]), Path(paths[TAGS_FILE])


def _download_with_progress(repo_id, filename, on_progress):
    try:
        total = get_hf_file_metadata(hf_hub_url(repo_id, filename)).size
    except Exception:
        total = None
    result = {}

    def run():
        try:
            result["path"] = hf_hub_download(repo_id, filename)
        except BaseException as error:  # re-raised on the calling thread
            result["error"] = error

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    blobs = Path(constants.HF_HUB_CACHE) / f"models--{repo_id.replace('/', '--')}" / "blobs"
    while worker.is_alive():
        done = sum(p.stat().st_size for p in blobs.glob("*.incomplete")) if blobs.exists() else 0
        on_progress(done // 2**20, total // 2**20 if total else None)
        worker.join(1.0)
    if "error" in result:
        raise result["error"]
    return result["path"]


class TagModel:
    def __init__(self, model_path, tags_path):
        options = ort.SessionOptions()
        options.log_severity_level = 3
        self.session = ort.InferenceSession(
            str(model_path), options, providers=["CUDAExecutionProvider"]
        )
        # Without CUDA, onnxruntime falls back to CPU with only a log line.
        self.on_gpu = self.session.get_providers()[0] == "CUDAExecutionProvider"
        model_input = self.session.get_inputs()[0]
        self.input_name = model_input.name
        size = model_input.shape[1]
        self.input_size = size if isinstance(size, int) else 448
        with open(tags_path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.names = [row["name"] for row in rows]
        self.categories = np.array([int(row["category"]) for row in rows])

    def predict(self, image_path):
        """Per-tag probabilities, aligned with self.names."""
        with Image.open(image_path) as img:
            x = preprocess(img, self.input_size)
        vec = self.session.run(None, {self.input_name: x})[0][0].astype(np.float32)
        if vec.min() >= 0.0 and vec.max() <= 1.0:
            return vec
        return 1.0 / (1.0 + np.exp(-vec))


def preprocess(img, size):
    """WD14 input: white background and padding to a square, BGR, float 0-255, NHWC."""
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGBA", img.size, (255, 255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
    h, w = rgb.shape[:2]
    m = max(h, w)
    top, left = (m - h) // 2, (m - w) // 2
    square = np.pad(
        rgb, ((top, m - h - top), (left, m - w - left), (0, 0)), constant_values=255
    )
    resized = Image.fromarray(square).resize((size, size), Image.BICUBIC)
    bgr = np.asarray(resized, dtype=np.float32)[:, :, ::-1]
    return np.ascontiguousarray(bgr)[np.newaxis]
