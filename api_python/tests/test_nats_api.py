import os
import sys
import json
import pytest
import nats

# --- Path Setup ---
current_dir = os.path.dirname(os.path.abspath(__file__))

# 1. Point to api_python/src so we can import nats_api
src_dir = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.append(src_dir)

# 2. Point to the OCR test images so we can feed the pipeline real bytes
ocr_images_dir = os.path.abspath(os.path.join(current_dir, "../../ocr/test_images"))

from nats_api import process_image_and_solve

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
    
    # SET UP A MOCK SERVICE LAYER
    # This fake listener pretends to be your Rust Service layer
    async def fake_rust_service_layer_callback(msg):
        # Optional: Verify the Python API sent us the right format
        received_payload = json.loads(msg.data.decode())
        assert "board" in received_payload, "NATS API did not package the board correctly"
        assert len(received_payload["board"]) == 9, "Board should have 9 rows"
        
        # Simulate the Rust layer sending back the solved JSON
        fake_reply = json.dumps({"board": expected_solution()}).encode()
        await nc.publish(msg.reply, fake_reply)
        
    sub = await nc.subscribe("sudoku.process", cb=fake_rust_service_layer_callback)
    
    # READ A REAL TEST IMAGE INTO BYTES
    test_image_path = os.path.join(ocr_images_dir, "test1.png")
    assert os.path.exists(test_image_path), f"Test image not found at {test_image_path}"
    
    with open(test_image_path, "rb") as f:
        image_bytes = f.read()
    
    try:
        # Trigger the function! 
        # This will run the OCR, hit our mock NATS subscriber, and return the result.
        result = await process_image_and_solve(image_bytes)
        
        # Verify the pipeline bundled both boards correctly
        assert "original_board" in result, "Result is missing the original_board"
        assert "solved_board" in result, "Result is missing the solved_board"
        
        # Verify the pipeline actually returned the solution we mocked
        assert result["solved_board"] == expected_solution(), "Did not return the solved board"
        
    finally:
        # Clean up the mock worker and connection
        await sub.unsubscribe()
        await nc.close()