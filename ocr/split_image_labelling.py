import os
from pathlib import Path

import cv2 as cv
import numpy as np
from matplotlib import pyplot as plt
from PIL import Image

from split_image import extract_numbered_cells
from digit_recog.digit_api import classify_digit


def show_labeled(labeled: list, n: int = 3, k: int = 3):
    """Display labelled cells in a 9x9 grid with predicted digits overlaid.

    Args:
        labeled: list of dicts from label_cells() with keys
                 'row', 'col', 'cell', 'label', 'confidence'.
        n: Number of blocks per row/column.
        k: Block size in cells.
    """
    grid_size = n * k
    fig, axes = plt.subplots(grid_size, grid_size, figsize=(8, 8))

    # Build a lookup from (row, col) -> entry
    lookup = {}
    for entry in labeled:
        lookup[(entry['row'], entry['col'])] = entry

    for r in range(grid_size):
        for c in range(grid_size):
            ax = axes[r, c]
            ax.axis('off')
            entry = lookup.get((r, c))
            if entry is None:
                continue
            cell = entry['cell']
            if len(cell.shape) == 3:
                display = cv.cvtColor(cell, cv.COLOR_BGR2RGB)
                ax.imshow(display)
            else:
                ax.imshow(cell, cmap='gray')

            text = str(entry['label']) if entry['label'] != 0 else ""
            ax.text(0.5, 0.5, text, fontsize=14, ha='center', va='center',
                    transform=ax.transAxes, color='red', fontweight='bold')

    plt.tight_layout()
    plt.show()


def label_cells(all_cells, confidence_threshold: float = 0.2):
    """Classify cells using the digit recognition model.

    Cells flagged ``has_digit`` are forwarded to the classifier;
    the rest are labelled 0 directly.  *all_cells* is mutated in place.

    Args:
        all_cells: List of dicts from ``extract_numbered_cells`` with keys
                   'row', 'col', 'cell', 'has_digit'.
        confidence_threshold: Minimum confidence to accept a non-zero digit
                              prediction. MNIST class 0 is skipped (not meaningful
                              for a 1-9 sudoku grid); the best non-zero prediction
                              must meet this threshold or the cell is labelled 0.

    Returns:
        The same list, each entry augmented with 'label' and 'confidence'.
    """
    if not all_cells:
        return []

    # Classify only cells the heuristic says have a digit
    digit_entries = [e for e in all_cells if e['has_digit']]
    cells_pil = []
    for entry in digit_entries:
        cell = entry['cell']
        rgb = cv.cvtColor(cell, cv.COLOR_BGR2RGB)
        alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)
        rgba = np.dstack((rgb, alpha))
        cells_pil.append(Image.fromarray(rgba, mode="RGBA"))

    predictions = classify_digit(cells_pil) if cells_pil else []

    for idx, entry in enumerate(digit_entries):
        # Skip MNIST class 0 (digit zero — not meaningful for a 1-9 sudoku grid)
        best = next((p for p in predictions[idx] if p["digit"] != 0), None)
        if best and best["confidence"] >= confidence_threshold:
            entry['label'] = best["digit"]
            entry['confidence'] = best["confidence"]

    # Fill in blank entries for cells without digits
    for entry in all_cells:
        if not entry.get('label'):
            entry['label'] = 0
            entry['confidence'] = 0.0

    return all_cells

def extract_grid(img_input, n: int = 3, k: int = 3,
                  confidence_threshold: float = 0.2):
    """Split a sudoku image, classify digits, and return the 9×9 grid.

    Args:
        img_input: File path (str) or numpy array.
        confidence_threshold: Minimum confidence to accept a non-zero digit
                              prediction (see ``label_cells``).
    Returns:
        (grid, labeled) tuple where:
          grid: list[list[int]] — 2D grid of shape (n*k × n*k), 0 = empty.
          labeled: list[dict] — per-cell dicts with 'row','col','cell','label','confidence'.
        Returns (None, None) if grid isolation fails.
    """
    cells = extract_numbered_cells(img_input, n, k)
    if not cells:
        return None, None
    labeled = label_cells(cells, confidence_threshold)
    grid_size = n * k
    grid = [[0] * grid_size for _ in range(grid_size)]
    for entry in labeled:
        grid[entry["row"]][entry["col"]] = entry["label"]
    return grid, labeled


if __name__ == "__main__":
    n, k = 3, 3

    script_dir = os.path.dirname(os.path.abspath(__file__))
    img_path = os.path.join(script_dir, "test_images", "test5easy.png")

    grid, labeled = extract_grid(img_path, n, k)
    if grid is None:
        print("Grid isolation failed.")
        exit()

    # Save misclassified cells for visual inspection
    out_dir = Path(script_dir) / "failing_cells"
    out_dir.mkdir(exist_ok=True)
    for entry in labeled:
        if entry['has_digit'] and entry['label'] == 0:
            gray = cv.cvtColor(entry['cell'], cv.COLOR_BGR2GRAY)
            Image.fromarray(gray, mode='L').save(
                out_dir / f"fail_r{entry['row']}_c{entry['col']}_conf{entry['confidence']:.3f}.png"
            )

    # Display labelled grid
    show_labeled(labeled, n, k)

    # Print the grid
    print("Sudoku grid (0 = blank):")
    for row in grid:
        print(" ".join(str(v) for v in row))
