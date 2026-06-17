"""End-to-end tests: extract a sudoku grid from each test image and verify the
extracted digit labels match the current expected output.

These freeze the current pipeline behaviour so regressions are caught.
"""

import os
import cv2
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from split_image_labelling import extract_grid
N = 3
K = 3
TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_images")


def _run_pipeline(img_file: str):
    """Run the OCR pipeline and return the 9×9 label grid (0 = blank)."""
    img_path = os.path.join(TEST_DIR, img_file)
    grid, _ = extract_grid(img_path, N, K)
    assert grid is not None, f"Grid isolation failed for {img_file}"
    return grid


# Expected outputs captured at pipeline version when these tests were written.
# Each entry: 9 rows of 9 ints (0 = empty cell).

EXPECTED = {
    "test1.png": [
        [4, 6, 0, 2, 0, 0, 0, 0, 0],
        [0, 0, 1, 6, 9, 0, 0, 0, 0],
        [0, 7, 8, 0, 0, 0, 0, 0, 0],
        [0, 0, 4, 0, 8, 0, 0, 0, 1],
        [9, 0, 0, 0, 0, 0, 0, 0, 7],
        [7, 0, 0, 0, 4, 0, 3, 0, 0],
        [0, 0, 0, 0, 0, 0, 6, 8, 0],
        [0, 0, 0, 0, 5, 9, 2, 0, 0],
        [0, 0, 0, 0, 0, 6, 0, 9, 3],
    ],
    "test2.png": [
        [0, 0, 0, 0, 0, 0, 1, 0, 0],
        [8, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 7, 0, 0, 0, 0, 0],
        [0, 3, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 4],
        [0, 0, 0, 0, 0, 5, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 2, 0],
        [0, 0, 0, 0, 4, 0, 0, 0, 0],
        [0, 0, 8, 0, 0, 0, 0, 0, 0],
    ],
    "test3.jpg": [
        [8, 0, 0, 0, 1, 0, 0, 0, 9],
        [0, 5, 0, 8, 0, 7, 0, 1, 0],
        [0, 0, 4, 0, 9, 0, 7, 0, 0],
        [0, 6, 0, 7, 0, 1, 0, 2, 0],
        [5, 0, 8, 0, 6, 0, 1, 0, 7],
        [0, 1, 0, 5, 0, 2, 0, 9, 0],
        [0, 0, 7, 0, 4, 0, 6, 0, 0],
        [0, 8, 0, 3, 0, 9, 0, 4, 0],
        [3, 0, 0, 0, 5, 0, 0, 0, 8],
    ],
    "test4.png": [
        [0, 3, 9, 1, 0, 0, 0, 0, 0],
        [4, 0, 8, 0, 6, 0, 0, 0, 2],
        [2, 0, 0, 5, 8, 0, 7, 0, 0],
        [8, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 2, 0, 0, 0, 9, 0, 0, 0],
        [3, 0, 6, 0, 0, 0, 0, 4, 9],
        [0, 0, 0, 0, 1, 0, 0, 3, 0],
        [0, 4, 0, 3, 0, 0, 0, 0, 8],
        [7, 0, 0, 0, 0, 0, 4, 0, 0],
    ],
    "test5easy.png": [
        [0, 0, 0, 0, 6, 0, 0, 0, 2],
        [4, 0, 0, 0, 1, 5, 6, 0, 0],
        [0, 0, 0, 7, 0, 0, 0, 9, 0],
        [0, 0, 0, 6, 0, 0, 1, 0, 7],
        [0, 7, 0, 0, 0, 0, 0, 8, 0],
        [3, 0, 6, 0, 0, 9, 0, 0, 0],
        [0, 5, 0, 0, 0, 8, 0, 0, 0],
        [0, 0, 1, 4, 9, 0, 0, 0, 3],
        [8, 0, 0, 0, 5, 0, 0, 0, 0],
    ],
    "test5full.png": [
        [0, 0, 0, 0, 6, 0, 0, 0, 2],
        [4, 0, 0, 0, 1, 5, 6, 0, 0],
        [0, 0, 0, 7, 0, 0, 0, 9, 0],
        [0, 0, 0, 6, 0, 0, 1, 0, 7],
        [0, 7, 0, 0, 0, 0, 0, 8, 0],
        [3, 0, 6, 0, 0, 9, 0, 0, 0],
        [0, 5, 0, 0, 0, 8, 0, 0, 0],
        [0, 0, 1, 4, 9, 0, 0, 0, 3],
        [8, 0, 0, 0, 5, 0, 0, 0, 0],
    ],
    "test7.png": [
        [3, 7, 6, 0, 0, 0, 0, 0, 4],
        [0, 0, 0, 0, 9, 3, 5, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0],
        [7, 5, 0, 0, 0, 0, 0, 6, 0],
        [2, 0, 8, 0, 4, 0, 0, 0, 7],
        [0, 0, 4, 6, 0, 0, 0, 0, 2],
        [0, 8, 0, 0, 5, 2, 0, 0, 0],
        [0, 2, 0, 7, 0, 8, 0, 0, 0],
        [0, 0, 0, 0, 3, 0, 0, 0, 0],
    ],
    "test8.png": [
        [3, 7, 6, 0, 0, 0, 0, 0, 4],
        [0, 0, 0, 0, 9, 3, 5, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0],
        [7, 5, 0, 0, 0, 0, 0, 6, 0],
        [2, 0, 8, 0, 4, 0, 0, 0, 7],
        [0, 0, 4, 6, 0, 0, 0, 0, 2],
        [0, 8, 0, 0, 5, 2, 0, 0, 0],
        [0, 2, 0, 7, 0, 8, 0, 0, 0],
        [0, 0, 0, 0, 3, 0, 0, 0, 0],
    ],
}


# --- Parametrized test -------------------------------------------------------

@pytest.mark.parametrize("img_file", list(EXPECTED.keys()))
def test_grid_from_image(img_file):
    grid = _run_pipeline(img_file)
    expected = EXPECTED[img_file]
    assert grid == expected, (
        f"Mismatch for {img_file}\n"
        f"  Expected:  {expected}\n"
        f"  Got:       {grid}"
    )


@pytest.mark.parametrize("img_file", list(EXPECTED.keys()))
def test_grid_from_raw_array(img_file):
    """Same as test_grid_from_image but passes a raw numpy array instead of path."""
    img_path = os.path.join(TEST_DIR, img_file)
    img = cv2.imread(img_path)
    assert img is not None, f"Could not load {img_file}"
    grid, _ = extract_grid(img, N, K)
    assert grid is not None, f"Grid isolation failed for {img_file} (raw array)"
    assert grid == EXPECTED[img_file], (
        f"Mismatch for {img_file} (raw array)\n"
        f"  Expected:  {EXPECTED[img_file]}\n"
        f"  Got:       {grid}"
    )
