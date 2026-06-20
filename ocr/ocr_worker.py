import asyncio
import hashlib
import time
import json
import os

import cv2
import nats
import numpy as np

from split_image_labelling import extract_grid, generate_overlay


def convert_to_rust_format(grid: list[list[int]]) -> list[list[str]]:
    rust_formatted_grid = []
    for row in grid:
        formatted_row = ["." if cell == 0 else str(cell) for cell in row]
        rust_formatted_grid.append(formatted_row)
    return rust_formatted_grid

def _save_failure(image_bytes: bytes) -> None:
    """Persist the failing image to /debug/grid_not_found for later inspection."""
    try:
        hash8 = hashlib.sha256(image_bytes).hexdigest()[:8]
        ts = int(time.time())
        os.makedirs("/debug/grid_not_found", exist_ok=True)
        path = f"/debug/grid_not_found/{ts}_{hash8}.png"
        with open(path, "wb") as f:
            f.write(image_bytes)
        print(f"Saved grid-not-found image to {path}")
    except Exception:
        pass


def _save_overlay(original_img, sudoku_corners, labeled: list, n: int, k: int,
                   image_bytes: bytes) -> None:
    """Generate and persist an overlay showing OCR predictions on the original photo."""
    try:
        hash8 = hashlib.sha256(image_bytes).hexdigest()[:8]
        ts = int(time.time())
        os.makedirs("/debug/ocr_overlays", exist_ok=True)
        overlay = generate_overlay(original_img, sudoku_corners, labeled, n, k)
        cv2.imwrite(f"/debug/ocr_overlays/{ts}_{hash8}.png", overlay)
    except Exception:
        pass


async def handle_ocr(msg):
    try:
        image_bytes = msg.data

        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            await nc.publish(
                msg.reply, json.dumps({"error": "Bad image"}).encode()
            )
            return

        headers = msg.headers or {}
        n = int(headers.get("n", 3))
        k = int(headers.get("k", 3))
        grid, labeled, _, sudoku_corners = extract_grid(img, n=n, k=k, confidence_threshold=0.55)
        if not grid:
            _save_failure(image_bytes)
            await nc.publish(
                msg.reply, json.dumps({"error": "No grid found"}).encode()
            )
            return

        rust_board = convert_to_rust_format(grid)
        _save_overlay(img, sudoku_corners, labeled, n, k, image_bytes)

        reply = json.dumps({"board": rust_board}).encode()
        await nc.publish(msg.reply, reply)

    except Exception as e:
        await nc.publish(
            msg.reply, json.dumps({"error": str(e)}).encode()
        )


async def main():
    global nc
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = await nats.connect(nats_url)
    await nc.subscribe("sudoku.ocr", cb=handle_ocr)
    print("OCR worker listening on sudoku.ocr")
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
