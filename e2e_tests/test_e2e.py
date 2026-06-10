import os
import time

import pytest
import requests

API_URL = "http://api:5000/solve-image"
TEST_IMAGE = os.path.join(os.path.dirname(__file__), "fixtures", "test1.png")


def _solve_image(files, **kwargs):
    """POST /solve-image, retrying on 500 (pipeline not ready yet)."""
    deadline = time.monotonic() + 45
    last_status = None
    while time.monotonic() < deadline:
        try:
            r = requests.post(API_URL, files=files, timeout=90, **kwargs)
        except requests.ConnectionError:
            time.sleep(2)
            continue
        if r.status_code == 200 or r.status_code == 400:
            return r
        last_status = r.status_code
        time.sleep(2)
    raise RuntimeError(
        f"Pipeline did not become ready within 45s (last status: {last_status})"
    )


@pytest.mark.e2e
def test_e2e_solve_image_returns_valid_boards():
    assert os.path.exists(TEST_IMAGE), f"Test image not found at {TEST_IMAGE}"

    with open(TEST_IMAGE, "rb") as f:
        image_bytes = f.read()

    files = {"image": ("test1.png", image_bytes, "image/png")}
    response = _solve_image(files)

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

    for row in solved:
        for cell in row:
            assert cell != ".", f"Solved board has empty cell: {solved}"


@pytest.mark.e2e
def test_e2e_solve_image_with_n_k_params():
    assert os.path.exists(TEST_IMAGE), f"Test image not found at {TEST_IMAGE}"

    with open(TEST_IMAGE, "rb") as f:
        image_bytes = f.read()

    files = {"image": ("test1.png", image_bytes, "image/png")}
    response = _solve_image(files, data={"n": "3", "k": "3"})

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    data = response.json()
    assert len(data["solved_board"]) == 9


@pytest.mark.e2e
def test_e2e_invalid_file_returns_400():
    files = {"image": ("test.txt", b"not an image", "text/plain")}
    response = _solve_image(files)
    assert response.status_code == 400
