"""Export each test image's flattened sudoku grid overlaid with the per-cell
bounding boxes used by the pipeline (``split``) and the predicted digit labels.

Output: one ``<stem>_overlay.png`` per test image written to ``ocr/testgrids/``.
These are visual-QA artifacts — they show exactly where the pipeline slices the
flattened grid and what digit it read in each cell.

Run from ``ocr/``::

    python export_testgrids.py
"""
import os
from pathlib import Path

import cv2 as cv

import preprocess as pp
from split_image_labelling import extract_grid

SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
TEST_DIR = SCRIPT_DIR / "test_images"
OUT_DIR = SCRIPT_DIR / "testgrids"
OUTRAGEOUS_DIR = TEST_DIR / "outrageous_images"
OUTRAGEOUS_OUT_DIR = OUT_DIR / "outrageous"
IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


def overlay_grid(flat_img, grid, n: int = 3, k: int = 3):
    """Draw cell bounding boxes and predicted labels onto a copy of ``flat_img``.

    Box geometry mirrors ``split_image.split``: a uniform ``n*k`` grid of
    ``slice_size = side / (n*k)`` squares. Block (``n``×``n``) separators are
    drawn thicker so the 3×3 structure is visible.
    """
    out = flat_img.copy()
    grid_size = n * k
    side = out.shape[0]
    slice_size = side // grid_size

    for r in range(grid_size):
        for c in range(grid_size):
            x0, y0 = c * slice_size, r * slice_size
            x1, y1 = x0 + slice_size, y0 + slice_size
            cv.rectangle(out, (x0, y0), (x1, y1), (0, 200, 0), 1)
            label = grid[r][c]
            if label:
                cv.putText(out, str(label), (x0 + 14, y0 + slice_size - 12),
                           cv.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # Thicker lines on block boundaries.
    for i in range(0, grid_size + 1, k):
        p = min(i * slice_size, side - 1)
        cv.line(out, (p, 0), (p, side), (255, 0, 0), 2)
        cv.line(out, (0, p), (side, p), (255, 0, 0), 2)
    return out


def export_image(img_path: Path, out_dir: Path = OUT_DIR) -> bool:
    """Run the pipeline on ``img_path`` and write its overlay. Returns success."""
    img = pp.load_image(str(img_path))
    if img is None:
        print(f"  skip {img_path.name}: could not load")
        return False

    flat_img = pp.do_preprocess(img)
    if flat_img is None:
        print(f"  skip {img_path.name}: grid isolation failed")
        return False

    grid, _ = extract_grid(img, 3, 3)
    if grid is None:
        print(f"  skip {img_path.name}: labelling failed")
        return False

    overlay = overlay_grid(flat_img, grid)
    out_path = out_dir / f"{img_path.stem}_overlay.png"
    cv.imwrite(str(out_path), overlay)
    print(f"  wrote {out_path.relative_to(SCRIPT_DIR)}")
    return True


def main():
    OUT_DIR.mkdir(exist_ok=True)
    images = sorted(p for p in TEST_DIR.iterdir()
                    if p.is_file() and p.suffix.lower() in IMG_EXTS)
    if not images:
        print(f"No test images found in {TEST_DIR}")
        return
    print(f"Exporting {len(images)} grid overlays to {OUT_DIR}")
    ok = sum(export_image(p) for p in images)
    print(f"Done: {ok}/{len(images)} overlays written")

    if OUTRAGEOUS_DIR.is_dir():
        OUTRAGEOUS_OUT_DIR.mkdir(parents=True, exist_ok=True)
        outrageous = sorted(p for p in OUTRAGEOUS_DIR.iterdir()
                            if p.is_file() and p.suffix.lower() in IMG_EXTS)
        if not outrageous:
            print(f"No outrageous images found in {OUTRAGEOUS_DIR}")
        else:
            print(f"\nExporting {len(outrageous)} outrageous overlays to {OUTRAGEOUS_OUT_DIR}")
            ok_out = sum(export_image(p, OUTRAGEOUS_OUT_DIR) for p in outrageous)
            print(f"Done: {ok_out}/{len(outrageous)} outrageous overlays written")


if __name__ == "__main__":
    main()
