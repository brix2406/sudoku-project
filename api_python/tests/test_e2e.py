import os
import time

import pytest
import requests

API_URL = "http://api:5000/solve-image"
TEST_IMAGE = os.path.join(os.path.dirname(__file__), "fixtures", "test1.png")

# Give the full stack a few seconds to stabilize (OCR worker retries DNS on startup)
SETUP_SLEEP = 5


@pytest.mark.e2e
def test_e2e_solve_image_returns_valid_boards():
    time.sleep(SETUP_SLEEP)
    assert os.path.exists(TEST_IMAGE), f"Test image not found at {TEST_IMAGE}"

    with open(TEST_IMAGE, "rb") as f:
        files = {"image": ("test1.png", f, "image/png")}
        response = requests.post(API_URL, files=files, timeout=90)

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data = response.json()
    assert "original_board" in data, "Response missing original_board"
    assert "solved_board" in data, "Response missing solved_board"

    original = data["original_board"]
    solved = data["solved_board"]
    assert len(original) == 9, f"original_board should have 9 rows, got {len(original)}"
    assert len(solved) == 9, f"solved_board should have 9 rows, got {len(solved)}"
    for row in original:
        assert len(row) == 9, f"each original row should have 9 cells, got {len(row)}"
    for row in solved:
        assert len(row) == 9, f"each solved row should have 9 cells, got {len(row)}"

    # The solved board should have no empty cells (no "." values)
    for row in solved:
        for cell in row:
            assert cell != ".", f"Solved board has empty cell: {solved}"


@pytest.mark.e2e
def test_e2e_solve_image_with_n_k_params():
    time.sleep(SETUP_SLEEP)
    assert os.path.exists(TEST_IMAGE), f"Test image not found at {TEST_IMAGE}"

    with open(TEST_IMAGE, "rb") as f:
        files = {"image": ("test1.png", f, "image/png")}
        data_fields = {"n": "3", "k": "3"}
        response = requests.post(
            API_URL, files=files, data=data_fields, timeout=90
        )

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    data = response.json()
    assert len(data["solved_board"]) == 9


@pytest.mark.e2e
def test_e2e_invalid_file_returns_400():
    files = {"image": ("test.txt", b"not an image", "text/plain")}
    response = requests.post(API_URL, files=files, timeout=10)
    assert response.status_code == 400
