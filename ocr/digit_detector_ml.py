"""
ML-based digit detector for sudoku cells.

Feature extraction MUST match train_digit_detector.py exactly.
Architecture MUST match the DigitDetector class in train_digit_detector.py.
"""

from pathlib import Path

import cv2 as cv
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

_HERE = Path(__file__).resolve().parent
_MODEL_PATH = _HERE / "digit_detector.pt"

_model: nn.Module | None = None
_mean: torch.Tensor | None = None
_std: torch.Tensor | None = None

FEATURE_DIM = 1027  # 32×32 pixels + 3 engineered


class DigitDetector(nn.Module):
    def __init__(self, n_features: int = FEATURE_DIM):
        super().__init__()
        self.fc1 = nn.Linear(n_features, 64)
        self.bn1 = nn.BatchNorm1d(64)
        self.fc2 = nn.Linear(64, 32)
        self.bn2 = nn.BatchNorm1d(32)
        self.fc3 = nn.Linear(32, 1)

    def forward(self, x):
        x = F.relu(self.bn1(self.fc1(x)))
        x = F.dropout(x, p=0.5, training=self.training)
        x = F.relu(self.bn2(self.fc2(x)))
        x = F.dropout(x, p=0.5, training=self.training)
        return self.fc3(x).squeeze(-1)


def _load_model():
    global _model, _mean, _std
    if _model is not None:
        return
    if not _MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found at {_MODEL_PATH}. Run train_digit_detector.py.")
    bundle = torch.load(str(_MODEL_PATH), map_location="cpu", weights_only=False)
    _model = DigitDetector()
    _model.load_state_dict(bundle["state_dict"])
    _model.eval()
    _mean = bundle["mean"]
    _std = bundle["std"]


def _extract_features(cell_bgr: np.ndarray) -> np.ndarray:
    gray = cv.cvtColor(cell_bgr, cv.COLOR_BGR2GRAY)
    h, w = gray.shape
    m = max(int(h * 0.02), 1)
    inner = gray[m:h - m, m:w - m]

    small = cv.resize(inner, (32, 32), interpolation=cv.INTER_NEAREST)
    pixels = small.astype(np.float32).ravel() / 255.0

    sobel = cv.Sobel(inner, cv.CV_64F, 1, 1, ksize=3)
    edge_density = np.float32(np.abs(sobel).mean() / 255.0)
    std = np.float32(inner.std() / 255.0)
    median = np.median(inner)
    dark_ratio = np.float32(np.count_nonzero(inner < median - 20) / inner.size)

    return np.concatenate([pixels, [edge_density, std, dark_ratio]])


def has_digit_ml(cell_bgr: np.ndarray) -> bool:
    _load_model()
    feats = _extract_features(cell_bgr)
    feats_norm = (feats - _mean.numpy()) / _std.numpy()
    x = torch.from_numpy(feats_norm).unsqueeze(0)
    with torch.no_grad():
        prob = torch.sigmoid(_model(x)).item()
    return prob >= 0.5


def has_digit_ml_batch(cells_bgr: list[np.ndarray]) -> list[bool]:
    if not cells_bgr:
        return []
    _load_model()
    feats = np.stack([_extract_features(c) for c in cells_bgr])
    feats_norm = (feats - _mean.numpy()) / _std.numpy()
    x = torch.from_numpy(feats_norm)
    with torch.no_grad():
        probs = torch.sigmoid(_model(x)).numpy()
    return (probs >= 0.5).tolist()
