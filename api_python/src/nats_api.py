import os
import sys
import json
import nats
from nats.errors import TimeoutError
import cv2 as cv
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
ocr_dir = os.path.abspath(os.path.join(current_dir, "../../ocr"))
sys.path.append(ocr_dir)

from split_image_labelling import extract_grid

def convert_to_rust_format(grid: list[list[int]]) -> list[list[str]]:
    """
    Converts the Python 0-based integer grid to Rust's String-based grid.
    Translates 0 -> "." and integers -> strings.
    """
    rust_formatted_grid = []
    for row in grid:
        formatted_row = ["." if cell == 0 else str(cell) for cell in row]
        rust_formatted_grid.append(formatted_row)
    return rust_formatted_grid

async def process_image_and_solve(image_bytes: bytes) -> dict:
    """
    1. Decodes image bytes.
    2. Runs extract_grid.
    3. Converts to Rust format.
    4. Sends to NATS.
    """
    # 1. Convert raw bytes to an OpenCV image in-memory
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv.imdecode(nparr, cv.IMREAD_COLOR)
    
    if img is None:
        raise ValueError("Could not decode image bytes into a valid image.")

    # 2. Extract the grid
    grid, labeled_data = extract_grid(img, n=3, k=3, confidence_threshold=0.5)
    
    if not grid:
        raise ValueError("Failed to isolate or read the Sudoku grid from the image.")

    # 3. Convert to the Rust format
    rust_board = convert_to_rust_format(grid)

    # 4. Connect to NATS
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = await nats.connect(nats_url)

    try:
        # Package the board exactly as Rust expects it
        payload = json.dumps({"board": rust_board}).encode()
        
        # Request solving from Rust service layer (10 second timeout)
        msg = await nc.request("sudoku.process", payload, timeout=10.0)
        
        # Decode the solved Sudoku JSON
        solved_data = json.loads(msg.data.decode())
        
        return {
            "original_board": rust_board,
            "solved_board": solved_data.get("board")
        }
        
    except TimeoutError:
        raise TimeoutError("Rust Service layer timed out while solving the puzzle.")
    finally:
        # Always gracefully close the NATS connection
        await nc.close()