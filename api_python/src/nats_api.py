import json
import os

import cv2
import nats
import numpy as np
from nats.errors import TimeoutError


async def process_image_and_solve(image_bytes: bytes, n: int = 3, k: int = 3) -> dict:
    # Validate image is decodable
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes into a valid image.")

    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = await nats.connect(nats_url)

    try:
        msg = await nc.request(
            "sudoku.process",
            image_bytes,
            timeout=60.0,
            headers={"n": str(n), "k": str(k)},
        )
        result = json.loads(msg.data.decode())
        if "error" in result:
            raise RuntimeError(result["error"])
        return {
            "original_board": result["original_board"],
            "solved_board": result["solved_board"],
        }
    except TimeoutError:
        raise TimeoutError("Service layer timed out while processing the image.")
    finally:
        await nc.close()
