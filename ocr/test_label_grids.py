"""End-to-end tests: extract a sudoku grid from each test image and verify the
extracted digit labels match the current expected output.

These freeze the current pipeline behaviour so regressions are caught.
"""

import os
import cv2
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from expected_grids import EXPECTED
from split_image_labelling import extract_grid
import preprocess
N = 3
K = 3
TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_images")


def _run_pipeline(img_file: str):
    """Run the OCR pipeline and return the 9×9 label grid (0 = blank)."""
    img_path = os.path.join(TEST_DIR, img_file)
    grid, _, _, _ = extract_grid(img_path, N, K)
    assert grid is not None, f"Grid isolation failed for {img_file}"
    return grid


# Expected outputs captured at pipeline version when these tests were written.
# Each entry: 9 rows of 9 ints (0 = empty cell).



def test_is_darkmode_detection():
    dark = cv2.imread(os.path.join(TEST_DIR, "darkmode.png"))
    light = cv2.imread(os.path.join(TEST_DIR, "test1.png"))
    assert dark is not None and light is not None
    assert preprocess.is_darkmode(dark) is True
    assert preprocess.is_darkmode(light) is False


# --- Parametrized tests -------------------------------------------------------

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
    grid, _, _, _ = extract_grid(img, N, K)
    assert grid is not None, f"Grid isolation failed for {img_file} (raw array)"
    assert grid == EXPECTED[img_file], (
        f"Mismatch for {img_file} (raw array)\n"
        f"  Expected:  {EXPECTED[img_file]}\n"
        f"  Got:       {grid}"
    )
