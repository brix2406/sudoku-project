import json
import os
import time

import cv2
import nats
import numpy as np
from nats.errors import TimeoutError, NoRespondersError


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

async def process_manual_and_solve(k: int, n: int, board: list) -> dict:
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = await nats.connect(nats_url)

    payload = json.dumps({"k": k, "n": n, "board": board})

    try:
        msg = await nc.request(
            "sudoku.manual_solve",
            payload.encode(),
            timeout=60.0,
        )
        result = json.loads(msg.data.decode())
        if "error" in result:
            raise RuntimeError(result["error"])
        return {
            "original_board": result["original_board"],
            "solved_board": result["solved_board"],
        }
    except NoRespondersError:
        raise RuntimeError(
            "No solver service is listening on 'sudoku.manual_solve'. "
            "Rebuild and restart the service layer container."
        )
    except TimeoutError:
        raise TimeoutError("Service layer timed out while solving the puzzle.")
    finally:
        await nc.close()


async def get_nats_status() -> dict:
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    try:
        nc = await nats.connect(nats_url)
    except Exception:
        return {
            'serviceStatus': 'offline',
            'workerStatus': 'disconnected',
            'latencyMs': 0,
            'queueDepth': 0,
        }
    try:
        t0 = time.monotonic()
        await nc.request("sudoku.ping", b"", timeout=1.0)
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {
            'serviceStatus': 'healthy',
            'workerStatus': 'connected',
            'latencyMs': latency_ms,
            'queueDepth': 0,
        }
    except NoRespondersError:
        return {
            'serviceStatus': 'offline',
            'workerStatus': 'disconnected',
            'latencyMs': 0,
            'queueDepth': 0,
        }
    except TimeoutError:
        return {
            'serviceStatus': 'degraded',
            'workerStatus': 'disconnected',
            'latencyMs': 0,
            'queueDepth': 0,
        }
    finally:
        await nc.close()
