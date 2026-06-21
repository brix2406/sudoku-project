"""Label verification tool: overlay truth grids on training images.

Usage: python3 ocr/verify_labels.py [--test-images] [--debug] [--all] [--image NAME]

Generates ocr/fail_images/verify_<name>.png showing detected grid
with the ground-truth digit/badge overlaid on each cell.
"""

import sys; sys.path.insert(0, 'ocr')
from pathlib import Path
import json, argparse
import cv2 as cv
import numpy as np

_HERE = Path(__file__).resolve().parent
DEBUG_DIR = _HERE.parent / 'debug'
TEST_DIR = _HERE / 'test_images'
OUT_DIR = _HERE / 'fail_images'
OUT_DIR.mkdir(exist_ok=True)

from expected_grids import EXPECTED
from split_image import extract_numbered_cells


def draw_truth_grid(img, grid, corners):
    """Overlay truth grid values on image with detected grid lines."""
    vis = img.copy()
    h, w = vis.shape[:2]

    if corners is not None and len(corners) == 4:
        pts = corners.squeeze().astype(np.float32)
        # Draw 9x9 grid lines
        for i in range(10):
            t = i / 9
            p0 = tuple((pts[0] + t * (pts[3] - pts[0])).astype(int))
            p1 = tuple((pts[1] + t * (pts[2] - pts[1])).astype(int))
            cv.line(vis, p0, p1, (0, 255, 0), 1)
            p0 = tuple((pts[0] + t * (pts[1] - pts[0])).astype(int))
            p1 = tuple((pts[3] + t * (pts[2] - pts[3])).astype(int))
            cv.line(vis, p0, p1, (0, 255, 0), 1)
        for pt in pts:
            cv.circle(vis, tuple(pt.astype(int)), 5, (0, 0, 255), -1)

    # Overlay digit text in each cell center
    if corners is not None and len(corners) == 4:
        pts = corners.squeeze().astype(np.float32)
        for r in range(9):
            for c in range(9):
                val = grid[r][c]
                if val == 0:
                    continue
                # Cell center via bilinear interpolation
                t = (c + 0.5) / 9
                u = (r + 0.5) / 9
                pt_top = pts[0] + t * (pts[1] - pts[0])
                pt_bot = pts[3] + t * (pts[2] - pts[3])
                center = (pt_top + u * (pt_bot - pt_top)).astype(int)
                cx, cy = center

                text = str(val)
                font_scale = min(w, h) / 350
                tw, th = cv.getTextSize(text, cv.FONT_HERSHEY_SIMPLEX, font_scale, 2)[0]
                cv.putText(vis, text, (cx - tw // 2, cy + th // 2),
                          cv.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 3)
                cv.putText(vis, text, (cx - tw // 2, cy + th // 2),
                          cv.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 255), 1)
    return vis


def verify_test_image(fname):
    img = cv.imread(str(TEST_DIR / fname))
    if img is None:
        print(f"  SKIP {fname}: cannot load")
        return
    grid = EXPECTED.get(fname)
    if grid is None:
        print(f"  SKIP {fname}: no EXPECTED entry")
        return

    cells, _, corners = extract_numbered_cells(img, 3, 3)
    vis = draw_truth_grid(img, grid, corners)

    h, w = vis.shape[:2]
    scale = min(1400 / max(h, w), 1.0)
    vis = cv.resize(vis, (int(w * scale), int(h * scale)))

    base = Path(fname).stem
    out = OUT_DIR / f'verify_test_{base}.png'
    cv.imwrite(str(out), vis)
    print(f"  {fname}")


def verify_debug_image(tf_path):
    gid = tf_path.stem.replace('_truth', '')
    orig = DEBUG_DIR / f'{gid}.png'
    if not orig.exists():
        return

    with open(tf_path) as f:
        raw = json.load(f)
    if not raw or raw == []:
        return
    truth = [[int(v) if v != '.' else 0 for v in r] for r in raw]

    img = cv.imread(str(orig))
    if img is None:
        return

    cells, _, corners = extract_numbered_cells(img, 3, 3)
    vis = draw_truth_grid(img, truth, corners)

    h, w = vis.shape[:2]
    scale = min(1400 / max(h, w), 1.0)
    vis = cv.resize(vis, (int(w * scale), int(h * scale)))

    out = OUT_DIR / f'verify_{gid}.png'
    cv.imwrite(str(out), vis)
    print(f"  {gid}.png")


def main():
    ap = argparse.ArgumentParser(description='Verify training labels')
    ap.add_argument('--test-images', action='store_true')
    ap.add_argument('--debug', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--image', type=str)
    args = ap.parse_args()

    if args.image:
        fname = args.image
        if fname in EXPECTED:
            verify_test_image(fname)
        else:
            tf = DEBUG_DIR / fname.replace('.png', '_truth.json')
            if tf.exists():
                verify_debug_image(tf)
            else:
                print(f"Unknown image: {fname}")
        return

    do_test = args.all or args.test_images
    do_debug = args.all or args.debug

    if do_test:
        print("=== Test images ===")
        for fname in sorted(EXPECTED.keys()):
            verify_test_image(fname)

    if do_debug:
        print("=== Debug images ===")
        for tf in sorted(DEBUG_DIR.glob('*_truth.json')):
            verify_debug_image(tf)

    print(f"\nSaved to {OUT_DIR}/")


if __name__ == '__main__':
    main()
