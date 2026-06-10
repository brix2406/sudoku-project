import base64
import json
import os

import nats
import pytest

from nats_api import process_image_and_solve


# Smallest valid 1x1 white PNG, base64-encoded
_VALID_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/"
    "PchI7wAAAABJRU5ErkJggg=="
)


def expected_solution():
    return [
        ["5", "3", "4", "6", "7", "8", "9", "1", "2"],
        ["6", "7", "2", "1", "9", "5", "3", "4", "8"],
        ["1", "9", "8", "3", "4", "2", "5", "6", "7"],
        ["8", "5", "9", "7", "6", "1", "4", "2", "3"],
        ["4", "2", "6", "8", "5", "3", "7", "9", "1"],
        ["7", "1", "3", "9", "2", "4", "8", "5", "6"],
        ["9", "6", "1", "5", "3", "7", "2", "8", "4"],
        ["2", "8", "7", "4", "1", "9", "6", "3", "5"],
        ["3", "4", "5", "2", "8", "6", "1", "7", "9"],
    ]


@pytest.mark.asyncio
async def test_nats_api_processes_image_and_gets_solution():
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = await nats.connect(nats_url)

    # Mock the service layer: listen on sudoku.process, receive raw image bytes,
    # and reply with a fake result.
    async def mock_service_layer(msg):
        # Verify payload contains raw image bytes (not empty)
        assert len(msg.data) > 0, "Image bytes should not be empty"

        reply = json.dumps(
            {
                "original_board": expected_solution(),
                "solved_board": expected_solution(),
            }
        ).encode()
        await nc.publish(msg.reply, reply)

    sub = await nc.subscribe("sudoku.process", cb=mock_service_layer)

    image_bytes = base64.b64decode(_VALID_PNG_B64)

    try:
        result = await process_image_and_solve(image_bytes, n=3, k=3)

        assert "original_board" in result, "Result is missing the original_board"
        assert "solved_board" in result, "Result is missing the solved_board"
        assert result["solved_board"] == expected_solution(), (
            "Did not return the solved board"
        )

    finally:
        await sub.unsubscribe()
        await nc.close()
