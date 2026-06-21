"""
Full pipeline visualization for a misclassified sudoku digit.
Shows every step from raw image → grid detection → cell extraction →
digit detection → MNIST preprocessing → digit classification → prediction.

Usage:
    python pipeline_viz.py
"""
import io, json, sys
from pathlib import Path

import cv2 as cv
import numpy as np
from PIL import Image
from matplotlib import pyplot as plt
from scipy import ndimage as ndi

_HERE = Path(__file__).resolve().parent
DEBUG_DIR = _HERE.parent / "debug"
OUT_DIR = _HERE.parent / "review" / "pipeline_viz"

sys.path.insert(0, str(_HERE))
from split_image import extract_numbered_cells
from split_image_labelling import label_cells
from preprocess import do_preprocess, flatten_img
from digit_detector.detector import has_digit_ml, _MODEL_PATH as detector_path

# ── target ────────────────────────────────────────────────────────────
GID = "1782036356_123e44b1"
TRUTH_ROW, TRUTH_COL = 2, 6   # 0-indexed; truth=1, pred=7


def preprocess_debug(cell_bgr: np.ndarray) -> dict:
    """Mirrors train_mnist.load_image() step-by-step, capturing intermediates."""
    rgb = cell_bgr.astype(np.float32)
    min_ch = rgb.min(axis=2)
    im = {"darkest": min_ch.copy()}

    flat = min_ch.ravel()
    is_grayscale = False

    t = float(flat.mean())
    for _ in range(10):
        m1 = float(flat[flat < t].mean()) if (flat < t).sum() > 0 else 0.0
        m2 = float(flat[flat >= t].mean()) if (flat >= t).sum() > 0 else 255.0
        tn = (m1 + m2) / 2.0
        if abs(tn - t) < 0.1:
            break
        t = tn
    if (min_ch < t).sum() / min_ch.size > 0.40:
        t = float(np.percentile(min_ch, 35))

    ink_mask = min_ch < t
    im["ink_mask"] = ink_mask.astype(np.uint8) * 255

    struct = np.ones((3, 3), dtype=bool)
    labeled, n_comp = ndi.label(ink_mask)
    h, w = min_ch.shape
    border_mask = np.zeros_like(labeled, dtype=bool)
    border_mask[0, :] = border_mask[-1, :] = True
    border_mask[:, 0] = border_mask[:, -1] = True

    best_comp, best_size, best_idx = None, 0, None
    largest_overall_size = 0
    for comp_id in range(1, n_comp + 1):
        comp_px = labeled == comp_id
        size = int(comp_px.sum())
        if size > largest_overall_size:
            largest_overall_size = size
        if size < 5:
            continue
        touches = bool(np.any(comp_px & border_mask))
        if not touches and size > best_size:
            best_size = size
            best_comp = comp_px
            best_idx = comp_id

    if best_comp is None or best_size < largest_overall_size * 0.25:
        cy0, cy1 = int(h * 0.2), int(h * 0.8)
        cx0, cx1 = int(w * 0.2), int(w * 0.8)
        center_region = np.zeros_like(ink_mask)
        center_region[cy0:cy1, cx0:cx1] = ink_mask[cy0:cy1, cx0:cx1]
        if center_region.sum() >= 5:
            best_comp = center_region
            best_size = int(center_region.sum())
            best_idx = None

    if best_comp is None and n_comp > 0:
        sizes = ndi.sum(ink_mask, labeled, range(1, n_comp + 1))
        best_idx = int(np.argmax(sizes)) + 1
        best_comp = labeled == best_idx

    # Components viz (green = selected, dim = rejected)
    comps_viz = np.zeros((h, w, 3), dtype=np.uint8)
    if n_comp > 0:
        colors = [(100, 100, 100), (255, 100, 0), (0, 100, 255), (255, 255, 0),
                  (255, 0, 255), (0, 255, 255), (128, 128, 255), (255, 128, 128)]
        for ci in range(1, n_comp + 1):
            color = (0, 255, 0) if ci == best_idx else colors[ci % len(colors)]
            comps_viz[labeled == ci] = color
    im["components"] = comps_viz

    if best_comp is None:
        for k in ("cropped", "inverted_padded", "final_28x28", "bimodal"):
            im[k] = np.zeros((1, 1), dtype=np.float32)
    else:
        best_d = ndi.binary_closing(best_comp, structure=struct, iterations=1)
        best_d = ndi.binary_dilation(best_d, structure=struct, iterations=1)
        rows = np.any(best_d, axis=1)
        cols = np.any(best_d, axis=0)
        y_min = max(0, int(np.where(rows)[0][0]) - 4)
        y_max = min(h - 1, int(np.where(rows)[0][-1]) + 4)
        x_min = max(0, int(np.where(cols)[0][0]) - 4)
        x_max = min(w - 1, int(np.where(cols)[0][-1]) + 4)
        crop_raw = min_ch[y_min:y_max + 1, x_min:x_max + 1]
        mask_crop = best_d[y_min:y_max + 1, x_min:x_max + 1]
        crop_clean = np.where(mask_crop, crop_raw, 255.0)
        im["cropped"] = crop_clean

        inv = 255.0 - crop_clean
        hc, wc = inv.shape
        side = max(hc, wc)
        py, px = (side - hc) // 2, (side - wc) // 2
        padded = np.zeros((side, side), dtype=np.float32)
        padded[py:py + hc, px:px + wc] = inv
        im["inverted_padded"] = padded

        pf = padded.ravel()
        t2 = pf.mean()
        for _ in range(10):
            m1 = pf[pf < t2].mean() if (pf < t2).sum() > 0 else 0.0
            m2 = pf[pf >= t2].mean() if (pf >= t2).sum() > 0 else 255.0
            tn = (m1 + m2) / 2.0
            if abs(tn - t2) < 0.1:
                break
            t2 = tn
        lo = pf[pf >= t2].min() if (pf >= t2).sum() > 0 else 0.0
        hi = padded.max()
        mapped = np.where(padded >= t2,
                          np.clip((padded - lo) / (hi - lo + 1e-6), 0, 1), 0.0)
        im["bimodal"] = (mapped * 255).astype(np.float32)

        img_28 = Image.fromarray((mapped * 255).astype(np.uint8)).resize(
            (28, 28), Image.BILINEAR)
        im["final_28x28"] = np.array(img_28, dtype=np.float32)

    im["threshold"] = t
    return im


def get_model_prediction(cell_bgr: np.ndarray) -> tuple:
    """Run the full digit_recog pipeline on a cell, return (top3, all_probs)."""
    from digit_recog.digit_api import _lazy_init, _load_image_fn, _predict_fn, _model
    import torch

    _lazy_init()

    # Convert cell → PIL RGBA → PNG bytes → load_image (same as classify_digit)
    rgba = cv.cvtColor(cell_bgr, cv.COLOR_BGR2RGBA)
    pil_img = Image.fromarray(rgba)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    tensor = _load_image_fn(buf)

    with torch.no_grad():
        logits = _model(tensor)
    probs = torch.softmax(logits, dim=1).cpu().numpy()[0]

    top3_idx = np.argsort(probs)[-3:][::-1]
    top3 = [{"digit": int(d), "confidence": float(probs[d])} for d in top3_idx]
    return top3, probs


def main():
    # Load image
    img_path = DEBUG_DIR / f"{GID}.png"
    img = cv.imread(str(img_path))
    if img is None:
        print(f"ERROR: cannot load {img_path}")
        return

    # Load truth
    truth_path = DEBUG_DIR / f"{GID}_truth.json"
    with open(truth_path) as f:
        truth = json.load(f)

    # ── Step 1+2: preprocess + extract grid ──
    grid_img, sudoku_corners = do_preprocess(img)
    if grid_img is None:
        print("ERROR: grid detection failed")
        return

    # ── Step 3: extract cells ──
    cells_data, _, _ = extract_numbered_cells(img, 3, 3)
    cells_data = label_cells(cells_data, confidence_threshold=0.0)

    # Find our target cell
    target = None
    for i, entry in enumerate(cells_data):
        if entry["row"] == TRUTH_ROW and entry["col"] == TRUTH_COL:
            target = entry
            break
    if target is None:
        print(f"ERROR: cell ({TRUTH_ROW},{TRUTH_COL}) not found")
        return

    truth_val = int(truth[TRUTH_ROW][TRUTH_COL])
    pred_val = target["label"]
    conf = target.get("confidence", 0)
    cell_bgr = target["cell"]

    # ── Step 4: digit detector ──
    try:
        has_digit = has_digit_ml(cell_bgr)
    except (FileNotFoundError, ImportError):
        has_digit = "N/A (model not trained)"
    # ── Step 5: MNIST preprocessing intermediates ──
    im = preprocess_debug(cell_bgr)

    # ── Step 6: model prediction ──
    top3, all_probs = get_model_prediction(cell_bgr)

    print(f"  cell ({TRUTH_ROW},{TRUTH_COL}): truth={truth_val}, pred={pred_val}, conf={conf:.4f}")
    print(f"  has_digit={has_digit}")
    print(f"  top3: {[(p['digit'], round(p['confidence'], 4)) for p in top3]}")
    print(f"  all_probs shape: {all_probs.shape}, sum={all_probs.sum():.4f}")
    fig = plt.figure(figsize=(20, 16))

    # Outer grid: 3 rows (context, preprocessing, results)
    gs_outer = fig.add_gridspec(3, 1, hspace=0.4, height_ratios=[1.0, 1.2, 0.9])

    fig.suptitle(
        f"Full Pipeline Visualization — truth={truth_val} → pred={pred_val}  "
        f"(misclass: 1→7)  |  cell ({TRUTH_ROW},{TRUTH_COL})  |  "
        f"has_digit={has_digit}  |  conf={conf:.3f}  |  thresh={im['threshold']:.0f}",
        fontsize=10, fontfamily="monospace", fontweight="bold", y=0.98)

    # ── Row 0: Context — original, flattened grid, cell, digit detector ──
    gs_ctx = gs_outer[0].subgridspec(1, 4, wspace=0.2)

    # Panel 0: Original image
    ax = fig.add_subplot(gs_ctx[0, 0])
    ax.imshow(cv.cvtColor(img, cv.COLOR_BGR2RGB))
    ax.set_title(f"1. Original Photo\n[{img.shape[1]}×{img.shape[0]}]",
                 fontsize=8, fontweight="bold")
    ax.annotate(f"Cell ({TRUTH_ROW},{TRUTH_COL})\ntruth=1  pred=7",
                xy=(0.5, 0.5), xycoords="axes fraction",
                ha="center", va="center",
                fontsize=9, fontweight="bold", color="red",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
    ax.axis("off")

    # Panel 1: Flattened grid
    ax = fig.add_subplot(gs_ctx[0, 1])
    ax.imshow(cv.cvtColor(grid_img, cv.COLOR_BGR2RGB))
    hg, wg = grid_img.shape[:2]
    gh, gw = hg / 9, wg / 9
    rect = plt.Rectangle((TRUTH_COL * gw, TRUTH_ROW * gh), gw, gh,
                          fill=False, edgecolor="red", linewidth=2.5)
    ax.add_patch(rect)
    ax.set_title("2. Flattened Grid", fontsize=8, fontweight="bold")
    ax.axis("off")

    # Panel 2: Extracted cell
    ax = fig.add_subplot(gs_ctx[0, 2])
    ax.imshow(cv.cvtColor(cell_bgr, cv.COLOR_BGR2RGB))
    ax.set_title(f"3. Cell [{cell_bgr.shape[1]}×{cell_bgr.shape[0]}]",
                 fontsize=8, fontweight="bold")
    ax.axis("off")

    # Panel 3: Digit detector
    ax = fig.add_subplot(gs_ctx[0, 3])
    ax.text(0.5, 0.5,
            f"4. Digit Detector\n(ML binary)\n\nhas_digit =\n{has_digit}",
            transform=ax.transAxes, ha="center", va="center",
            fontsize=14, fontfamily="monospace", fontweight="bold",
            color="green" if has_digit else "red")
    ax.set_title("Digit Detector", fontsize=8, fontweight="bold")
    ax.axis("off")

    # ── Row 1: MNIST preprocessing — 7 steps ──────────────────────────
    gs_pre = gs_outer[1].subgridspec(1, 7, wspace=0.15)

    steps = [
        ("darkest",        "5. Darkest Ch\nmin(R,G,B)", "gray"),
        ("ink_mask",       f"6. Ink Mask\nthr={im['threshold']:.0f}", "gray"),
        ("components",     "7. Components\ngreen=selected", None),
        ("cropped",        "8. Cropped\n+ masked", "gray"),
        ("inverted_padded","9. Inverted\n+ padded", "gray"),
        ("bimodal",        "10. Bimodal\nFG stretch", "gray"),
        ("final_28x28",    "11. 28×28\n→ CNN input", "gray"),
    ]

    for j, (key, title, cmap) in enumerate(steps):
        ax = fig.add_subplot(gs_pre[0, j])
        arr = im.get(key)
        if arr is not None:
            if cmap == "gray":
                ax.imshow(arr, cmap="gray", vmin=0, vmax=255)
            else:
                ax.imshow(arr)
        ax.set_title(title, fontsize=6.5, fontfamily="monospace")
        ax.axis("off")

    # ── Row 2: Results — probability bar chart + summary ──────────────
    gs_res = gs_outer[2].subgridspec(1, 2, wspace=0.2, width_ratios=[1.4, 1])

    # Bar chart
    ax_bar = fig.add_subplot(gs_res[0, 0])
    digits = list(range(10))
    colors = ["#1f77b4"] * 10
    colors[truth_val] = "#2ca02c"   # green for truth
    colors[pred_val] = "#d62728"     # red for misprediction
    bars = ax_bar.bar(digits, all_probs, color=colors)
    ax_bar.set_xticks(digits)
    ax_bar.set_xlabel("Digit Class", fontsize=9)
    ax_bar.set_ylabel("Probability", fontsize=9)
    ax_bar.set_title("12. CNN Output: P(digit | image)", fontsize=9, fontweight="bold")
    ax_bar.set_ylim(0, max(1.0, all_probs.max() * 1.15))
    for d, prob in enumerate(all_probs):
        if prob > 0.03:
            ax_bar.annotate(f"{prob:.3f}", (d, prob),
                            textcoords="offset points", xytext=(0, 4),
                            ha="center", fontsize=6, fontfamily="monospace")

    # Summary panel
    ax_sum = fig.add_subplot(gs_res[0, 1])
    ax_sum.axis("off")

    lines = [
        f"Grid:  row={TRUTH_ROW}, col={TRUTH_COL}",
        f"",
        f"Truth:     {truth_val}",
        f"Predicted: {pred_val}  ← WRONG",
        f"Conf:      {conf:.4f}",
        f"Has digit: {has_digit}",
        f"",
        f"Top-3 predictions:",
    ]
    for i, p in enumerate(top3):
        tag = ""
        if p["digit"] == truth_val:
            tag = " ← TRUTH"
        elif p["digit"] == pred_val:
            tag = " ← PREDICTED"
        lines.append(f"  #{i+1}: {p['digit']}  ({p['confidence']:.4f}){tag}")
    lines += [
        f"",
        f"Cell: {cell_bgr.shape[1]}×{cell_bgr.shape[0]} px",
        f"Threshold: {im['threshold']:.1f}",
    ]

    ax_sum.text(0.05, 0.95, "\n".join(lines),
                transform=ax_sum.transAxes, va="top", ha="left",
                fontsize=8.5, fontfamily="monospace",
                bbox=dict(boxstyle="round,pad=0.5", facecolor="#f5f5f5", alpha=0.9))


    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{GID}_r{TRUTH_ROW}c{TRUTH_COL}_pipeline.png"
    plt.savefig(str(out_path), dpi=120, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"Saved → {out_path}")
    print(f"  Size: {out_path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
