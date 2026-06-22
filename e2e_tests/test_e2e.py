import os
import time

import pytest
import requests

API_URL = "http://api:5000/solve-image"
MANUAL_URL = "http://api:5000/manual_solve"
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


def _manual_solve(json_data, **kwargs):
    """POST /manual_solve, retrying on 500 (pipeline not ready yet)."""
    deadline = time.monotonic() + 45
    last_status = None
    while time.monotonic() < deadline:
        try:
            r = requests.post(MANUAL_URL, json=json_data, timeout=90, **kwargs)
        except requests.ConnectionError:
            time.sleep(2)
            continue
        if r.status_code in (200, 400, 422):
            return r
        last_status = r.status_code
        time.sleep(2)
    raise RuntimeError(
        f"Pipeline did not become ready within 45s (last status: {last_status})"
    )


EXPECTED_ORIGINAL_9X9 = [
    ["5","3",".",".","7",".",".",".","."],
    ["6",".",".","1","9","5",".",".","."],
    [".","9","8",".",".",".",".","6","."],
    ["8",".",".",".","6",".",".",".","3"],
    ["4",".",".","8",".","3",".",".","1"],
    ["7",".",".",".","2",".",".",".","6"],
    [".","6",".",".",".",".","2","8","."],
    [".",".",".","4","1","9",".",".","5"],
    [".",".",".",".","8",".",".","7","9"],
]


def _is_valid_solution(board: list[list[str]], clues: list[list[str]]) -> bool:
    """Return True if board is a valid sudoku solution respecting clues."""
    n = len(board)
    k = int(n ** 0.5)  # box size for standard sudoku
    digits = {str(d) for d in range(1, n + 1)}

    # Every cell must be filled with a valid digit
    for r in range(n):
        for c in range(n):
            if board[r][c] not in digits:
                return False

    # Rows must not repeat
    for r in range(n):
        if set(board[r]) != digits:
            return False

    # Columns must not repeat
    for c in range(n):
        col = [board[r][c] for r in range(n)]
        if set(col) != digits:
            return False

    # Boxes must not repeat
    for br in range(k):
        for bc in range(k):
            box = []
            for r in range(br * k, (br + 1) * k):
                for c in range(bc * k, (bc + 1) * k):
                    box.append(board[r][c])
            if set(box) != digits:
                return False

    # Must respect all clue positions
    for r in range(n):
        for c in range(n):
            if clues[r][c] != "." and board[r][c] != clues[r][c]:
                return False

    return True


@pytest.mark.e2e
def test_e2e_manual_solve_returns_valid_boards():
    puzzle = (
        "Sudoku{(3,3)"
        "(5,3,.,.,7,.,.,.,.,"
        "6,.,.,1,9,5,.,.,.,"
        ".,9,8,.,.,.,.,6,.,"
        "8,.,.,.,6,.,.,.,3,"
        "4,.,.,8,.,3,.,.,1,"
        "7,.,.,.,2,.,.,.,6,"
        ".,6,.,.,.,.,2,8,.,"
        ".,.,.,4,1,9,.,.,5,"
        ".,.,.,.,8,.,.,7,9)"
        "}"
    )
    response = _manual_solve({"sudoku_string": puzzle})

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data = response.json()
    assert "original_board" in data, "Response missing original_board"
    assert "solved_board" in data, "Response missing solved_board"

    original = data["original_board"]
    solved = data["solved_board"]

    assert original == EXPECTED_ORIGINAL_9X9, (
        f"original_board does not match sent puzzle.\n"
        f"Expected: {EXPECTED_ORIGINAL_9X9}\n"
        f"Got:      {original}"
    )

    assert _is_valid_solution(solved, original), (
        "solved_board is not a valid sudoku solution "
        "respecting the original clues"
    )

@pytest.mark.e2e
def test_e2e_manual_solve_bad_format_returns_422():
    response = _manual_solve({"sudoku_string": "NotAValidFormat"})
    assert response.status_code == 422, (
        f"Expected 422, got {response.status_code}: {response.text}"
    )


@pytest.mark.e2e
def test_e2e_manual_solve_missing_field_returns_400():
    response = _manual_solve({"other_field": "value"})
    assert response.status_code == 400, (
        f"Expected 400, got {response.status_code}: {response.text}"
    )
