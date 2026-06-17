import asyncio
import json
import os

import cv2
import nats
import numpy as np

from split_image_labelling import extract_grid


def convert_to_rust_format(grid: list[list[int]]) -> list[list[str]]:
    rust_formatted_grid = []
    for row in grid:
        formatted_row = ["." if cell == 0 else str(cell) for cell in row]
        rust_formatted_grid.append(formatted_row)
    return rust_formatted_grid


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

        grid, _ = extract_grid(img, n=n, k=k, confidence_threshold=0.5)
        if not grid:
            await nc.publish(
                msg.reply, json.dumps({"error": "No grid found"}).encode()
            )
            return

        rust_board = convert_to_rust_format(grid)
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
