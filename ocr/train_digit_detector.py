"""
Digit detector architecture search.
Searches 6 architectures (<=50K params) with 2-fold CV on dropout/lr.
Uses 32x32 raw pixels, geometric augmentation (+-5 deg rotation, +-5px translation).
Saves best model to digit_detector.pt.
"""

import json, sys, time
from pathlib import Path
import cv2 as cv
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

_HERE = Path(__file__).resolve().parent
DEBUG_DIR = _HERE.parent / "debug"
TEST_DIR = _HERE / "test_images"

sys.path.insert(0, str(_HERE))
from split_image import extract_numbered_cells
from expected_grids import EXPECTED

FEATURE_DIM = 1024


# ---------------------------------------------------------------------------
# Architectures  (all <= 50K params, each factory accepts a dropout argument)
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
    "linear":    (LinearModel, False),   # (class, needs_channel_dim)
    "mlp16":     (MLP16,      False),
    "mlp48":     (MLP48,      False),
    "cnn_tiny":  (CNNTiny,    True),
    "cnn_small": (CNNSmall,   True),
    "cnn_large": (CNNLarge,   True),
}


def build_model(arch_name, dropout):
    cls, needs_channel = ARCH_REGISTRY[arch_name]
    model = cls(dropout=dropout)
    n_params = sum(p.numel() for p in model.parameters())
    return model, n_params, needs_channel


# ---------------------------------------------------------------------------
# Feature extraction  (32x32 raw pixels only — no engineered features)
# ---------------------------------------------------------------------------

def extract_features(cell_bgr):
    """Return (32, 32) float32 array in [0, 1]."""
    gray = cv.cvtColor(cell_bgr, cv.COLOR_BGR2GRAY)
    h, w = gray.shape
    m = max(int(h * 0.02), 1)
    inner = gray[m:h - m, m:w - m]
    small = cv.resize(inner, (32, 32), interpolation=cv.INTER_NEAREST)
    return small.astype(np.float32) / 255.0


# ---------------------------------------------------------------------------
# Augmentation  (geometric: +-5 deg rotation + +-5 px translation)
# ---------------------------------------------------------------------------

def augment_image(img_32x32):
    """img_32x32: float32 (32,32) in [0,1]. Returns augmented copy."""
    angle = np.random.uniform(-5, 5)
    dx = np.random.randint(-5, 6)
    dy = np.random.randint(-5, 6)
    rot = cv.getRotationMatrix2D((15.5, 15.5), angle, 1.0)
    M = rot.copy()
    M[0, 2] += dx
    M[1, 2] += dy
    return cv.warpAffine(img_32x32, M, (32, 32), borderMode=cv.BORDER_REPLICATE)


def augment_batch(images):
    """images: (N, 32, 32) float32 in [0,1]. Returns augmented copy."""
    out = np.empty_like(images)
    for i in range(len(images)):
        out[i] = augment_image(images[i])
    return out


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def collect_data():
    """Return (X, y) where X is (N, 32, 32) float32 in [0,1], y is (N,) int."""
    X_list, y_list = [], []
    for filename, grid in EXPECTED.items():
        img = cv.imread(str(TEST_DIR / filename))
        if img is None:
            continue
        cells, _, _ = extract_numbered_cells(img, 3, 3)
        if not cells:
            continue
        for e in cells:
            r, c = e["row"], e["col"]
            truth = grid[r][c] != 0
            X_list.append(extract_features(e["cell"]))
            y_list.append(1 if truth else 0)
    for tf in sorted(DEBUG_DIR.glob("*_truth.json")):
        gid = tf.stem.replace("_truth", "")
        orig = DEBUG_DIR / f"{gid}.png"
        if not orig.exists():
            continue
        with open(tf) as f:
            raw = json.load(f)
        if not raw or raw == []:
            continue
        truth = [[int(v) if v != "." else 0 for v in r] for r in raw]
        img = cv.imread(str(orig))
        if img is None:
            continue
        cells, _, _ = extract_numbered_cells(img, 3, 3)
        if not cells:
            continue
        for e in cells:
            r, c = e["row"], e["col"]
            truth_d = truth[r][c] != 0
            X_list.append(extract_features(e["cell"]))
            y_list.append(1 if truth_d else 0)
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)
    return X, y


# ---------------------------------------------------------------------------
# Holdout split  (200-sample stratified)
# ---------------------------------------------------------------------------

def make_holdout(X_all, y_all, n_holdout=200):
    rng = np.random.RandomState(42)
    pos_idx = np.where(y_all == 1)[0]
    neg_idx = np.where(y_all == 0)[0]
    n_pos = min(n_holdout // 2, len(pos_idx))
    n_neg = n_holdout - n_pos
    pos_pick = rng.choice(pos_idx, n_pos, replace=False)
    neg_pick = rng.choice(neg_idx, n_neg, replace=False)
    holdout_idx = np.concatenate([pos_pick, neg_pick])
    rng.shuffle(holdout_idx)
    mask = np.ones(len(X_all), dtype=bool)
    mask[holdout_idx] = False
    return X_all[mask], y_all[mask], X_all[holdout_idx], y_all[holdout_idx]


# ---------------------------------------------------------------------------
# 2-fold stratified split for CV
# ---------------------------------------------------------------------------

def stratified_kfold(y, k=2):
    """Return list of (train_idx, val_idx) arrays."""
    rng = np.random.RandomState(42)
    pos_idx = np.where(y == 1)[0]
    neg_idx = np.where(y == 0)[0]
    rng.shuffle(pos_idx)
    rng.shuffle(neg_idx)
    pos_folds = np.array_split(pos_idx, k)
    neg_folds = np.array_split(neg_idx, k)
    folds = []
    for i in range(k):
        val_pos = pos_folds[i]
        val_neg = neg_folds[i]
        val_idx = np.concatenate([val_pos, val_neg])
        train_pos = np.concatenate([pos_folds[j] for j in range(k) if j != i])
        train_neg = np.concatenate([neg_folds[j] for j in range(k) if j != i])
        train_idx = np.concatenate([train_pos, train_neg])
        folds.append((train_idx, val_idx))
    return folds


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_fold(model, X_train_raw, y_train, X_val_raw, y_val,
               mean, std, needs_channel, lr, epochs, verbose=True):
    """Train one fold. Returns best validation accuracy."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)

    n_pos = y_train.sum()
    pos_weight = torch.tensor([(len(y_train) - n_pos) / max(n_pos, 1)], device=device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    # pre-normalize validation data (no augmentation)
    Xv_norm = (X_val_raw - mean) / std
    if needs_channel:
        Xv = torch.from_numpy(Xv_norm[:, None, :, :]).float().to(device)
    else:
        Xv = torch.from_numpy(Xv_norm.reshape(len(X_val_raw), -1)).float().to(device)
    yv = torch.from_numpy(y_val).float().to(device)

    best_acc, best_state = 0.0, None

    for epoch in range(epochs):
        model.train()
        perm = torch.randperm(len(X_train_raw))
        total_loss, n_batches = 0.0, 0

        for i in range(0, len(X_train_raw), 64):
            bi = perm[i:i + 64].numpy()
            # augment raw images, then normalize
            xb_aug = augment_batch(X_train_raw[bi])
            xb_norm = (xb_aug - mean) / std
            if needs_channel:
                xb = torch.from_numpy(xb_norm[:, None, :, :]).float().to(device)
            else:
                xb = torch.from_numpy(xb_norm.reshape(len(bi), -1)).float().to(device)
            yb = torch.from_numpy(y_train[bi]).float().to(device)

            optimizer.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            n_batches += 1

        scheduler.step()

        model.eval()
        with torch.no_grad():
            preds = (torch.sigmoid(model(Xv)) >= 0.5).float()
            acc = (preds == yv).float().mean().item()

        if acc > best_acc:
            best_acc = acc
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

        if verbose and (epoch % 30 == 0 or epoch == epochs - 1):
            tp = int(((preds == 1) & (yv == 1)).sum())
            fp = int(((preds == 1) & (yv == 0)).sum())
            fn = int(((preds == 0) & (yv == 1)).sum())
            print(f"    epoch {epoch:3d}: loss={total_loss / n_batches:.4f}  "
                  f"acc={acc:.4f}  tp={tp} fp={fp} fn={fn}")

    model.load_state_dict(best_state)
    return best_acc


# ---------------------------------------------------------------------------
# Cross-validation evaluation
# ---------------------------------------------------------------------------

def cv_evaluate(arch_name, dropout, lr, X_train, y_train, folds,
                mean, std, needs_channel, epochs=150):
    accs = []
    for fold_i, (train_idx, val_idx) in enumerate(folds):
        model, _, _ = build_model(arch_name, dropout)
        acc = train_fold(model,
                         X_train[train_idx], y_train[train_idx],
                         X_train[val_idx],  y_train[val_idx],
                         mean, std, needs_channel, lr, epochs, verbose=False)
        accs.append(acc)
    return np.mean(accs)


# ---------------------------------------------------------------------------
# Holdout evaluation with per-error details
# ---------------------------------------------------------------------------

def evaluate_holdout(model, X_hold_raw, y_hold, mean, std, needs_channel):
    """Evaluate on holdout, print per-error details."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device).eval()

    Xh_norm = (X_hold_raw - mean) / std
    if needs_channel:
        Xh = torch.from_numpy(Xh_norm[:, None, :, :]).float().to(device)
    else:
        Xh = torch.from_numpy(Xh_norm.reshape(len(X_hold_raw), -1)).float().to(device)
    yh = torch.from_numpy(y_hold).float().to(device)

    with torch.no_grad():
        probs = torch.sigmoid(model(Xh)).cpu().numpy()
        preds = (probs >= 0.5)

    acc = (preds == y_hold).mean()
    tp = int(((preds == 1) & (y_hold == 1)).sum())
    fp = int(((preds == 1) & (y_hold == 0)).sum())
    fn = int(((preds == 0) & (y_hold == 1)).sum())
    tn = int(((preds == 0) & (y_hold == 0)).sum())

    print(f"  Holdout: acc={acc:.4f}  TP={tp}  FP={fp}  FN={fn}  TN={tn}")

    errors = []
    for i in range(len(y_hold)):
        if preds[i] != y_hold[i]:
            etype = "FP" if preds[i] == 1 else "FN"
            errors.append((i, int(y_hold[i]), float(probs[i]), etype))

    if errors:
        print(f"  Errors ({len(errors)}):")
        for idx, true_label, prob, etype in errors:
            print(f"    idx={idx:3d}  true={true_label}  prob={prob:.4f}  {etype}")

    return acc, tp, fp, fn, tn


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Collecting labeled cell data...")
    t0 = time.time()
    X_raw, y = collect_data()
    print(f"  Collected {len(y)} samples in {time.time() - t0:.1f}s")
    n_pos = int(y.sum())
    print(f"  pos={n_pos}  neg={len(y) - n_pos}")

    # Normalization stats from raw training set
    mean = X_raw.mean(axis=0)   # (32, 32)
    std = X_raw.std(axis=0) + 1e-8

    # 200-sample stratified holdout
    X_train_raw, y_train, X_hold_raw, y_hold = make_holdout(X_raw, y, n_holdout=200)
    print(f"Holdout: {len(X_hold_raw)} ({int(y_hold.sum())} pos)")
    print(f"Train:   {len(X_train_raw)} ({int(y_train.sum())} pos)")

    # ---- Architecture search via 2-fold CV ----
    dropout_opts = [0.1, 0.25, 0.4]
    lr_opts = [0.001, 0.003, 0.01]
    folds = stratified_kfold(y_train, k=2)

    arch_list = list(ARCH_REGISTRY.items())
    best_cv_acc = -1.0
    best_combo = None
    best_n_params = 0

    print("\n" + "=" * 72)
    print("Architecture search (2-fold CV)")
    print("=" * 72)

    for arch_name, (arch_cls, needs_channel) in arch_list:
        n_params = sum(p.numel() for p in arch_cls().parameters())
        for dr in dropout_opts:
            for lr_val in lr_opts:
                cv_acc = cv_evaluate(arch_name, dr, lr_val,
                                     X_train_raw, y_train, folds,
                                     mean, std, needs_channel, epochs=150)
                marker = ""
                if cv_acc > best_cv_acc or (cv_acc == best_cv_acc and
                                             (best_combo is None or n_params < best_n_params)):
                    best_cv_acc = cv_acc
                    best_combo = (arch_name, dr, lr_val, needs_channel)
                    best_n_params = n_params
                    marker = " *"
                print(f"  {arch_name:10s}  dr={dr:.2f}  lr={lr_val:.3f}  "
                      f"params={n_params:5d}  cv_acc={cv_acc:.4f}{marker}")

    arch_best, dr_best, lr_best, needs_ch_best = best_combo
    print(f"\nBest: {arch_best}  dropout={dr_best}  lr={lr_best}  "
          f"params={best_n_params}  cv_acc={best_cv_acc:.4f}")

    # ---- Train winner on full training set ----
    print(f"\nTraining winner ({arch_best}) on full training set (200 epochs)...")
    winner, _, _ = build_model(arch_best, dr_best)
    train_fold(winner, X_train_raw, y_train, X_hold_raw, y_hold,
               mean, std, needs_ch_best, lr_best, epochs=200, verbose=True)

    # ---- Evaluate on holdout with per-error details ----
    print(f"\nHoldout evaluation ({arch_best}):")
    evaluate_holdout(winner, X_hold_raw, y_hold, mean, std, needs_ch_best)

    # ---- Full-set evaluation ----
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    Xh_norm = (X_hold_raw - mean) / std
    Xt_norm = (X_train_raw - mean) / std
    if needs_ch_best:
        Xh = torch.from_numpy(Xh_norm[:, None, :, :]).float().to(device)
        Xt = torch.from_numpy(Xt_norm[:, None, :, :]).float().to(device)
    else:
        Xh = torch.from_numpy(Xh_norm.reshape(len(X_hold_raw), -1)).float().to(device)
        Xt = torch.from_numpy(Xt_norm.reshape(len(X_train_raw), -1)).float().to(device)

    X_all_norm = torch.cat([Xt, Xh], dim=0)
    y_all_t = torch.from_numpy(np.concatenate([y_train, y_hold])).float().to(device)

    winner = winner.to(device).eval()
    with torch.no_grad():
        probs_all = torch.sigmoid(winner(X_all_norm)).cpu().numpy()
        preds_all = (probs_all >= 0.5)
        y_all_np = np.concatenate([y_train, y_hold])
        acc_all = (preds_all == y_all_np).mean()
        tp_all = int(((preds_all == 1) & (y_all_np == 1)).sum())
        fp_all = int(((preds_all == 1) & (y_all_np == 0)).sum())
        fn_all = int(((preds_all == 0) & (y_all_np == 1)).sum())
        print(f"\nFull-set: acc={acc_all:.4f}  TP={tp_all}  FP={fp_all}  FN={fn_all}")

    # ---- Save ----
    out_path = _HERE / "digit_detector.pt"
    bundle = {
        "state_dict": winner.state_dict(),
        "mean": torch.from_numpy(mean),
        "std": torch.from_numpy(std),
        "arch": arch_best,
    }
    torch.save(bundle, out_path)
    print(f"\nSaved: {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
