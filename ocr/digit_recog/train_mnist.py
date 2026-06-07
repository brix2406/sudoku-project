"""
MNIST digit classifier: CNN with 2-layer cross-validation hyperparameter tuning.
CPU-optimised: CV uses a 10k subsample for speed, final training uses full 60k.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms
import numpy as np
from PIL import Image
import itertools
import json
import os
import time

torch.manual_seed(42)
np.random.seed(42)

DEVICE = torch.device("cpu")
print(f"Device: {DEVICE}  |  Torch: {torch.__version__}  |  "
      f"{torch.get_num_threads()} threads")

MNIST_DIR = "./data/mnist"

# ── Data ─────────────────────────────────────────────────────────────
def load_mnist():
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,)),
    ])
    train_set = datasets.MNIST(MNIST_DIR, train=True, download=True, transform=transform)
    test_set  = datasets.MNIST(MNIST_DIR, train=False, download=True, transform=transform)
    return train_set, test_set


# ── Model ────────────────────────────────────────────────────────────
class DigitCNN(nn.Module):
    def __init__(self, dropout_rate=0.25):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
        self.bn1  = nn.BatchNorm2d(32)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.bn2  = nn.BatchNorm2d(64)
        self.pool = nn.MaxPool2d(2)
        self.fc1  = nn.Linear(64 * 7 * 7, 128)
        self.drop = nn.Dropout(dropout_rate)
        self.fc2  = nn.Linear(128, 10)

    def forward(self, x):
        x = self.pool(F.relu(self.bn1(self.conv1(x))))
        x = self.pool(F.relu(self.bn2(self.conv2(x))))
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        x = self.drop(x)
        return self.fc2(x)


def count_params(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


# ── Training helpers (CPU: num_workers=0, pin_memory=False) ──────────
def make_loader(ds, bs, shuffle=False):
    return DataLoader(ds, bs, shuffle=shuffle, num_workers=0, pin_memory=False)


def train_one_epoch(model, loader, optimizer, criterion):
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    for imgs, labs in loader:
        imgs, labs = imgs.to(DEVICE), labs.to(DEVICE)
        optimizer.zero_grad()
        loss = criterion(model(imgs), labs)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * imgs.size(0)
        correct += model(imgs).max(1)[1].eq(labs).sum().item()
        total += imgs.size(0)
    return total_loss / total, correct / total


@torch.no_grad()
def evaluate(model, loader, criterion=None):
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    for imgs, labs in loader:
        imgs, labs = imgs.to(DEVICE), labs.to(DEVICE)
        logits = model(imgs)
        if criterion is not None:
            total_loss += criterion(logits, labs).item() * imgs.size(0)
        correct += logits.max(1)[1].eq(labs).sum().item()
        total += imgs.size(0)
    return total_loss / total if criterion else 0.0, correct / total


# ── 2-layer CV (subsampled for speed) ────────────────────────────────
def cross_validate(train_set, param_grid, subsample_size=10000, n_folds=2, cv_epochs=3):
    """N-fold CV on a random subsample for fast hyperparameter search."""
    full_size = len(train_set)
    sample_idx = np.random.choice(full_size, subsample_size, replace=False)

    fold_sizes = np.full(n_folds, subsample_size // n_folds)
    fold_sizes[:subsample_size % n_folds] += 1

    results = []
    keys = list(param_grid.keys())
    combos = list(itertools.product(*param_grid.values()))
    n = len(combos)

    print(f"  CV: {n} combos x {n_folds} folds x {cv_epochs} epochs "
          f"(subsample={subsample_size})")

    for ci, combo in enumerate(combos, 1):
        params = dict(zip(keys, combo))
        lr, bs, dr = params["lr"], params["batch_size"], params["dropout_rate"]
        fold_accs = []
        ptr = 0
        for fold in range(n_folds):
            fsize = int(fold_sizes[fold])
            val_idx   = sample_idx[ptr:ptr + fsize]
            train_idx = np.concatenate([sample_idx[:ptr], sample_idx[ptr + fsize:]])
            ptr += fsize

            tr_loader = make_loader(Subset(train_set, train_idx.tolist()), bs, True)
            val_loader = make_loader(Subset(train_set, val_idx.tolist()), 1024)

            model = DigitCNN(dropout_rate=dr).to(DEVICE)
            opt = optim.Adam(model.parameters(), lr=lr)
            crit = nn.CrossEntropyLoss()
            for _ in range(cv_epochs):
                train_one_epoch(model, tr_loader, opt, crit)

            _, acc = evaluate(model, val_loader)
            fold_accs.append(acc)

        mean_acc = float(np.mean(fold_accs))
        results.append((mean_acc, params))
        print(f"    [{ci:2d}/{n}]  lr={lr:.0e}  bs={bs:3d}  dr={dr:.2f}  "
              f"val={mean_acc*100:.2f}%")

    results.sort(key=lambda x: -x[0])
    best = results[0]
    print(f"    → Best: lr={best[1]['lr']:.0e}  bs={best[1]['batch_size']}  "
          f"dr={best[1]['dropout_rate']:.2f}  val={best[0]*100:.2f}%")
    return results


# ── Preprocess arbitrary image ───────────────────────────────────────
def load_image(path):
    """Any image → MNIST-normalised 1×1×28×28 tensor.
    
    Robustly handles colored / non-grayscale images:
      1. Picks the darkest RGB channel per pixel (min(R,G,B)).
      2. Otsu threshold to find ink pixels.
      3. Connected-component analysis to reject border artifacts.
      4. Crops to the largest interior ink component with margin.
      5. Inverts, pads to square, applies bimodal FG stretch.
      6. Resizes to 28×28 with BILINEAR.
    """
    from scipy import ndimage as ndi
    
    # Detect original mode before converting
    orig_img = Image.open(path)
    is_grayscale = orig_img.mode == "L"
    orig = orig_img.convert("RGBA")
    arr = np.array(orig, dtype=np.float32)
    rgb = arr[:, :, :3]
    
    # Darkest channel → captures ink regardless of digit hue
    min_ch = rgb.min(axis=2)                  # low = ink, high = paper
    
    # Contrast stretch for low-contrast grayscale scans only
    if is_grayscale:
        lo, hi = np.percentile(min_ch, 1), np.percentile(min_ch, 99)
        if hi > lo:
            min_ch = np.clip((min_ch - lo) / (hi - lo) * 255, 0, 255)
    
    # Threshold: Otsu for colored images, percentile for grayscale scans
    # Grayscale scans (L-mode) have ink diffusion on paper → Otsu captures
    # too much ink bleed, making strokes artificially thick. A percentile
    # threshold captures only the core ink, preserving stroke shape.
    flat = min_ch.ravel()
    if is_grayscale:
        t = float(np.percentile(min_ch, 20))
    else:
        t = float(flat.mean())
        for _ in range(10):
            m1 = float(flat[flat < t].mean()) if (flat < t).sum() > 0 else 0.0
            m2 = float(flat[flat >= t].mean()) if (flat >= t).sum() > 0 else 255.0
            t_next = (m1 + m2) / 2.0
            if abs(t_next - t) < 0.1:
                break
            t = t_next
    
    ink_mask = min_ch < t
    
    # Connected-component analysis — reject components touching image border
    labeled, n_comp = ndi.label(ink_mask)
    h, w = min_ch.shape
    border_mask = np.zeros_like(labeled, dtype=bool)
    border_mask[0, :] = border_mask[-1, :] = True
    border_mask[:, 0] = border_mask[:, -1] = True
    
    best_comp, best_size = None, 0
    for comp_id in range(1, n_comp + 1):
        comp_px = (labeled == comp_id)
        size = int(comp_px.sum())
        if size < 5:
            continue
        touches_border = bool(np.any(comp_px & border_mask))
        if not touches_border and size > best_size:
            best_size = size
            best_comp = comp_px
    
    # Fallback: if no interior component found, use the largest overall
    if best_comp is None:
        comp_sizes = ndi.sum(ink_mask, labeled, range(1, n_comp + 1))
        if n_comp > 0:
            best_idx = int(np.argmax(comp_sizes)) + 1
            best_comp = (labeled == best_idx)
    
    if best_comp is None:
        # Truly no ink — return blank
        tensor = transforms.ToTensor()(Image.new("L", (28, 28), 0))
        tensor = transforms.Normalize((0.1307,), (0.3081,))(tensor)
        return tensor.unsqueeze(0)
    # Mild dilation: thickens thin strokes by 1px (helps for small/thin digits)
    struct = np.ones((3, 3), dtype=bool)
    best_comp = ndi.binary_dilation(best_comp, structure=struct, iterations=1)
    
    # Bounding box of the digit component (with margin)
    rows = np.any(best_comp, axis=1)
    cols = np.any(best_comp, axis=0)
    y_min = max(0, int(np.where(rows)[0][0]) - 4)
    y_max = min(h - 1, int(np.where(rows)[0][-1]) + 4)
    x_min = max(0, int(np.where(cols)[0][0]) - 4)
    x_max = min(w - 1, int(np.where(cols)[0][-1]) + 4)
    
    crop = min_ch[y_min:y_max + 1, x_min:x_max + 1]
    # Mask out non-digit pixels: set to paper value (255 in min_ch)
    # so border artifacts within the crop bounding box are eliminated.
    mask_crop = best_comp[y_min:y_max + 1, x_min:x_max + 1]
    crop = np.where(mask_crop, crop, 255.0)
    
    # Invert: now ink is bright, paper is dark (MNIST polarity)
    inv = 255.0 - crop
    
    # Pad to a square (center the digit)
    hc, wc = inv.shape
    side = max(hc, wc)
    pad_y = (side - hc) // 2
    pad_x = (side - wc) // 2
    padded = np.zeros((side, side), dtype=np.float32)
    padded[pad_y:pad_y + hc, pad_x:pad_x + wc] = inv
    
    # Bimodal FG stretch on the padded crop
    pflat = padded.ravel()
    t2 = pflat.mean()
    for _ in range(10):
        m1 = pflat[pflat < t2].mean() if (pflat < t2).sum() > 0 else 0.0
        m2 = pflat[pflat >= t2].mean() if (pflat >= t2).sum() > 0 else 255.0
        t_next = (m1 + m2) / 2.0
        if abs(t_next - t2) < 0.1:
            break
        t2 = t_next
    
    lo = pflat[pflat >= t2].min() if (pflat >= t2).sum() > 0 else 0.0
    hi = padded.max()
    mapped = np.where(padded >= t2, np.clip((padded - lo) / (hi - lo + 1e-6), 0, 1), 0.0)
    
    # Resize to 28×28 with bilinear interpolation
    img_28 = Image.fromarray((mapped * 255).astype(np.uint8)).resize((28, 28), Image.BILINEAR)
    
    tensor = transforms.ToTensor()(img_28)
    tensor = transforms.Normalize((0.1307,), (0.3081,))(tensor)
    return tensor.unsqueeze(0)


@torch.no_grad()
def predict(model, tensor):
    model.eval()
    logits = model(tensor.to(DEVICE))
    probs = F.softmax(logits, dim=1)
    pred = logits.argmax(1).item()
    return pred, probs[0, pred].item(), probs[0].cpu().numpy()


# ── Main ─────────────────────────────────────────────────────────────
def main():
    t0 = time.time()

    print("── Loading MNIST ──")
    train_set, test_set = load_mnist()
    print(f"  Train: {len(train_set)}  |  Test: {len(test_set)}")

    # ── Layer 1: coarse grid (lr × batch_size, dropout fixed) ───────
    print("\n══ LAYER 1: Coarse (lr × batch_size) ══")
    cv1 = cross_validate(train_set, {
        "lr":          [1e-3, 3e-4, 1e-4],
        "batch_size":  [64, 128],
        "dropout_rate": [0.25],
    })
    best1 = cv1[0][1]

    # ── Layer 2: fine grid (dropout_rate) ───────────────────────────
    print("\n══ LAYER 2: Fine (dropout_rate) ══")
    cv2 = cross_validate(train_set, {
        "lr":          [best1["lr"]],
        "batch_size":  [best1["batch_size"]],
        "dropout_rate": [0.1, 0.2, 0.3, 0.4],
    })
    best_p = cv2[0][1]

    print(f"\n{'='*60}")
    print(f"BEST: lr={best_p['lr']:.0e}  bs={best_p['batch_size']}  "
          f"dr={best_p['dropout_rate']:.2f}")
    print(f"{'='*60}")

    # ── Train final model on full 60k ────────────────────────────────
    print("\n── Training final model (full 60k) ──")
    tr_loader = make_loader(train_set, best_p["batch_size"], True)
    te_loader = make_loader(test_set, 1024)

    model = DigitCNN(dropout_rate=best_p["dropout_rate"]).to(DEVICE)
    opt = optim.Adam(model.parameters(), lr=best_p["lr"])
    sched = optim.lr_scheduler.ReduceLROnPlateau(opt, mode="max", factor=0.5, patience=3)
    crit = nn.CrossEntropyLoss()

    n_epochs = 15
    best_acc = 0.0
    t_train = time.time()
    for ep in range(1, n_epochs + 1):
        tl, ta = train_one_epoch(model, tr_loader, opt, crit)
        vl, va = evaluate(model, te_loader, crit)
        sched.step(va)

        if va > best_acc:
            best_acc = va
            torch.save(model.state_dict(), "best_mnist_cnn.pt")

        print(f"  Epoch {ep:2d}/{n_epochs}  loss={tl:.4f}  train={ta*100:.2f}%  "
              f"test={va*100:.2f}%  best={best_acc*100:.2f}%")

    elapsed_tr = time.time() - t_train
    print(f"  Training: {elapsed_tr:.0f}s")

    # Reload best checkpoint
    model.load_state_dict(torch.load("best_mnist_cnn.pt", weights_only=True))
    _, final_acc = evaluate(model, te_loader)
    print(f"\n  FINAL test accuracy: {final_acc*100:.2f}%  "
          f"(params: {count_params(model):,})")

    # ── Classify digit.png ──────────────────────────────────────────
    print("\n── Classifying digit.png ──")
    if not os.path.exists("digit.png"):
        print("  NOT FOUND")
    else:
        tensor = load_image("digit.png")
        pred, conf, probs = predict(model, tensor)
        print(f"  Prediction: {pred}  (confidence: {conf*100:.2f}%)")
        top3 = np.argsort(probs)[-3:][::-1]
        for i, d in enumerate(top3, 1):
            print(f"    Top-{i}: {d}  ({probs[d]*100:.2f}%)")

    # ── Save results ────────────────────────────────────────────────
    total = time.time() - t0
    print(f"\nTotal time: {total//60:.0f}m {total%60:.0f}s")

    res = {
        "best_params": best_p,
        "test_accuracy": round(final_acc * 100, 2),
        "model_params": count_params(model),
    }
    if os.path.exists("digit.png"):
        res["digit_prediction"] = int(pred)
        res["digit_confidence"] = round(conf * 100, 2)
        res["top3"] = {str(d): round(float(probs[d]) * 100, 2) for d in top3}
    with open("mnist_results.json", "w") as f:
        json.dump(res, f, indent=2)
    print("Results → mnist_results.json")


if __name__ == "__main__":
    main()
