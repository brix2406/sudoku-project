"""ML-based digit detector for sudoku cells. Architecture dispatched from saved bundle."""

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
_needs_channel: bool = False
FEATURE_DIM = 1024


# ---------------------------------------------------------------------------
# Architectures  (must match train_digit_detector.py exactly)
# ---------------------------------------------------------------------------

class LinearModel(nn.Module):
    def __init__(self, dropout=0.0):
        super().__init__()
        self.fc = nn.Linear(1024, 1)

    def forward(self, x):
        return self.fc(x).squeeze(-1)


class MLP16(nn.Module):
    def __init__(self, dropout=0.25):
        super().__init__()
        self.fc1 = nn.Linear(1024, 16)
        self.bn1 = nn.BatchNorm1d(16)
        self.fc2 = nn.Linear(16, 1)
        self.dropout = dropout

    def forward(self, x):
        x = F.relu(self.bn1(self.fc1(x)))
        x = F.dropout(x, p=self.dropout, training=self.training)
        return self.fc2(x).squeeze(-1)


class MLP48(nn.Module):
    def __init__(self, dropout=0.25):
        super().__init__()
        self.fc1 = nn.Linear(1024, 48)
        self.bn1 = nn.BatchNorm1d(48)
        self.fc2 = nn.Linear(48, 1)
        self.dropout = dropout

    def forward(self, x):
        x = F.relu(self.bn1(self.fc1(x)))
        x = F.dropout(x, p=self.dropout, training=self.training)
        return self.fc2(x).squeeze(-1)


class CNNTiny(nn.Module):
    def __init__(self, dropout=0.25):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 4, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(4)
        self.conv2 = nn.Conv2d(4, 8, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(8)
        self.pool = nn.MaxPool2d(2)
        self.avgpool = nn.AdaptiveAvgPool2d((4, 4))
        self.fc = nn.Linear(8 * 4 * 4, 1)
        self.dropout = dropout

    def forward(self, x):
        x = self.pool(F.relu(self.bn1(self.conv1(x))))
        x = self.pool(F.relu(self.bn2(self.conv2(x))))
        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        x = F.dropout(x, p=self.dropout, training=self.training)
        return self.fc(x).squeeze(-1)


class CNNSmall(nn.Module):
    def __init__(self, dropout=0.25):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 8, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(8)
        self.conv2 = nn.Conv2d(8, 16, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(16)
        self.pool = nn.MaxPool2d(2)
        self.avgpool = nn.AdaptiveAvgPool2d((4, 4))
        self.fc = nn.Linear(16 * 4 * 4, 1)
        self.dropout = dropout

    def forward(self, x):
        x = self.pool(F.relu(self.bn1(self.conv1(x))))
        x = self.pool(F.relu(self.bn2(self.conv2(x))))
        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        x = F.dropout(x, p=self.dropout, training=self.training)
        return self.fc(x).squeeze(-1)


class CNNLarge(nn.Module):
    def __init__(self, dropout=0.25):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 16, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(16)
        self.conv2 = nn.Conv2d(16, 32, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(32)
        self.conv3 = nn.Conv2d(32, 64, 3, padding=1)
        self.bn3 = nn.BatchNorm2d(64)
        self.pool = nn.MaxPool2d(2)
        self.avgpool = nn.AdaptiveAvgPool2d((4, 4))
        self.fc = nn.Linear(64 * 4 * 4, 1)
        self.dropout = dropout

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = self.pool(x)
        x = F.relu(self.bn3(self.conv3(x)))
        x = self.pool(x)
        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        x = F.dropout(x, p=self.dropout, training=self.training)
        return self.fc(x).squeeze(-1)


ARCH_REGISTRY = {
    "linear":    (LinearModel, False),
    "mlp16":     (MLP16,      False),
    "mlp48":     (MLP48,      False),
    "cnn_tiny":  (CNNTiny,    True),
    "cnn_small": (CNNSmall,   True),
    "cnn_large": (CNNLarge,   True),
}


# ---------------------------------------------------------------------------
# Feature extraction  (32x32 raw pixels only)
# ---------------------------------------------------------------------------

def _extract_features(cell_bgr):
    """Return (32, 32) float32 array in [0, 1]."""
    gray = cv.cvtColor(cell_bgr, cv.COLOR_BGR2GRAY)
    h, w = gray.shape
    m = max(int(h * 0.02), 1)
    inner = gray[m:h - m, m:w - m]
    small = cv.resize(inner, (32, 32), interpolation=cv.INTER_NEAREST)
    return small.astype(np.float32) / 255.0


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def _load_model():
    global _model, _mean, _std, _needs_channel
    if _model is not None:
        return
    if not _MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {_MODEL_PATH}")
    bundle = torch.load(str(_MODEL_PATH), map_location="cpu", weights_only=False)
    arch = bundle["arch"]
    cls, needs_channel = ARCH_REGISTRY[arch]
    _model = cls()
    _model.load_state_dict(bundle["state_dict"])
    _model.eval()
    _mean = bundle["mean"]
    _std = bundle["std"]
    _needs_channel = needs_channel


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def has_digit_ml(cell_bgr):
    _load_model()
    feats = _extract_features(cell_bgr)           # (32, 32) float32 in [0,1]
    feats_t = torch.from_numpy(feats)
    feats_norm = (feats_t - _mean) / _std         # (32, 32)
    if _needs_channel:
        x = feats_norm.unsqueeze(0).unsqueeze(0)  # (1, 1, 32, 32)
    else:
        x = feats_norm.reshape(1, -1)              # (1, 1024)
    with torch.no_grad():
        return torch.sigmoid(_model(x)).item() >= 0.5


def has_digit_ml_batch(cells_bgr):
    if not cells_bgr:
        return []
    _load_model()
    feats = np.stack([_extract_features(c) for c in cells_bgr])  # (N, 32, 32)
    feats_t = torch.from_numpy(feats)
    feats_norm = (feats_t - _mean) / _std
    if _needs_channel:
        x = feats_norm.unsqueeze(1)   # (N, 1, 32, 32)
    else:
        x = feats_norm.reshape(len(cells_bgr), -1)  # (N, 1024)
    with torch.no_grad():
        return (torch.sigmoid(_model(x)).numpy() >= 0.5).tolist()
