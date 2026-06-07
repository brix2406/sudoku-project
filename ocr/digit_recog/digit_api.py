"""
digit_api.py — Reusable digit recognition API.

Usage:
    from digit_api import classify_digit

    # From file path
    result = classify_digit("test_digits/4_digit.png")

    # From raw bytes (e.g. uploaded file, HTTP request body)
    with open("test_digits/4_digit.png", "rb") as f:
        result = classify_digit(f.read())

    # From a PIL Image
    from PIL import Image
    img = Image.open("test_digits/4_digit.png")
    result = classify_digit(img)

    Returns:
        [
            {"digit": 4, "confidence": 0.9999},
            {"digit": 9, "confidence": 0.0001},
            {"digit": 8, "confidence": 0.0000},
        ]
        (sorted descending by confidence, top-3)
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import List, Dict, Union

import numpy as np
import torch
from PIL import Image

_HERE = Path(__file__).parent
_MODEL_PATH = _HERE / "best_mnist_cnn.pt"

# Lazy-loaded globals
_model = None
_load_image_fn = None
_predict_fn = None


def _lazy_init():
    global _model, _load_image_fn, _predict_fn
    if _model is not None:
        return

    from .train_mnist import DigitCNN, load_image, predict

    if not _MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Trained model not found at {_MODEL_PATH}. "
            "Run `python3 train_mnist.py` first."
        )

    _model = DigitCNN(dropout_rate=0.3)
    _model.load_state_dict(
        torch.load(str(_MODEL_PATH), weights_only=True, map_location="cpu")
    )
    _model.eval()

    _load_image_fn = load_image
    _predict_fn = predict


def classify_digit(
    source: Union[
        str, Path, bytes, Image.Image,
        List[Union[Image.Image, bytes, str, Path]],
    ],
) -> Union[List[Dict[str, Union[int, float]]], List[List[Dict[str, Union[int, float]]]]]:
    """
    Classify a digit image (or a list of images) and return top-3 predictions.

    Parameters
    ----------
    source : str | Path | bytes | PIL.Image | list[PIL.Image | bytes | str | Path]
        One of:
        - file path (str or Path)
        - raw image bytes
        - single PIL Image
        - **list** of PIL Images, raw bytes, or file paths (batched inference)

    Returns
    -------
    list[dict]
        Top-3 predictions for a single input, each with keys ``digit`` (int)
        and ``confidence`` (float, 0-1).  Sorted descending by confidence.
    list[list[dict]]
        If a list of PIL Images was passed, returns a list of results, one
        per image, in the same order.

    Raises
    ------
    FileNotFoundError  IsADirectoryError  TypeError  ValueError
    """
    _lazy_init()

    # --- List branch (parallel preprocessing + batched inference) ---
    if isinstance(source, list):
        if not source:
            return []

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _resolve_item(item):
            """Convert any accepted input type → load_image() input."""
            if isinstance(item, Image.Image):
                buf = io.BytesIO()
                item.save(buf, format="PNG")
                buf.seek(0)
                return buf
            if isinstance(item, bytes):
                return io.BytesIO(item)
            if isinstance(item, (str, Path)):
                p = Path(item)
                if not p.exists():
                    raise FileNotFoundError(f"Image not found: {item}")
                return str(p)
            raise TypeError(
                f"Each item in list must be PIL.Image, bytes, or str/Path, "
                f"got {type(item).__name__}"
            )

        tensors = [None] * len(source)
        with ThreadPoolExecutor(max_workers=min(len(source), 8)) as pool:
            futures = {
                pool.submit(_load_image_fn, _resolve_item(item)): i
                for i, item in enumerate(source)
            }
            for future in as_completed(futures):
                idx = futures[future]
                tensors[idx] = future.result()

        batch = torch.cat(tensors, dim=0)
        with torch.no_grad():
            logits = _model(batch)
        probs_all = torch.softmax(logits, dim=1).cpu().numpy()
        results = []
        for probs in probs_all:
            top3_idx = np.argsort(probs)[-3:][::-1]
            results.append([
                {"digit": int(d), "confidence": float(probs[d])}
                for d in top3_idx
            ])
        return results

    # --- Single-input branch (backward compatible) ---
    if isinstance(source, (str, Path)):
        source = str(source)
        src_path = Path(source)
        if src_path.is_dir():
            raise IsADirectoryError(
                f"Expected an image file, got a directory: {source}"
            )
        if not src_path.exists():
            raise FileNotFoundError(f"Image not found: {source}")
        tensor = _load_image_fn(source)

    elif isinstance(source, bytes):
        tensor = _load_image_fn(io.BytesIO(source))

    elif isinstance(source, Image.Image):
        buf = io.BytesIO()
        source.save(buf, format="PNG")
        buf.seek(0)
        tensor = _load_image_fn(buf)

    else:
        raise TypeError(
            f"Expected str, Path, bytes, PIL.Image, or list[PIL.Image], "
            f"got {type(source).__name__}"
        )

    _, _, probs = _predict_fn(_model, tensor)
    top3_idx = np.argsort(probs)[-3:][::-1]
    return [
        {"digit": int(d), "confidence": float(probs[d])}
        for d in top3_idx
    ]
