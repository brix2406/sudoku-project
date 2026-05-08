import os
import json
import pytest
import nats

def mock_puzzle():
    return {
        "size": 3,
        "board": [
            [".", "3", ".", ".", "7", ".", ".", ".", "."],
            ["6", ".", ".", "1", "9", "5", ".", ".", "."],
            [".", "9", "8", ".", ".", ".", ".", "6", "."],
            ["8", ".", ".", ".", "6", ".", ".", ".", "3"],
            ["4", ".", ".", "8", ".", "3", ".", ".", "1"],
            ["7", ".", ".", ".", "2", ".", ".", ".", "6"],
            [".", "6", ".", ".", ".", ".", "2", "8", "."],
            [".", ".", ".", "4", "1", "9", ".", ".", "5"],
            [".", ".", ".", ".", "8", ".", ".", "7", "9"],
        ]
    }

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
async def test_python_api_can_request_and_receive_nats_solution():
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = await nats.connect(nats_url)
    
    # SET UP A MOCK WORKER
    # We create a fake listener in Python that instantly replies to any request
    async def fake_rust_worker_callback(msg):
        # We simulate the Rust worker sending back the solved JSON
        fake_reply = json.dumps({"board": expected_solution()}).encode()
        await nc.publish(msg.reply, fake_reply)
        
    sub = await nc.subscribe("sudoku.solve", cb=fake_rust_worker_callback)
    
    payload = json.dumps(mock_puzzle()).encode()
    
    try:
        # Since the fake worker is in the same file, this will resolve instantly
        response = await nc.request("sudoku.solve", payload, timeout=2.0)
        
        solved_sudoku = json.loads(response.data.decode())
        
        assert solved_sudoku.get("board") == expected_solution(), "Python API did not correctly parse the reply"
        
    finally:
        # Clean up the mock worker and connection
        await sub.unsubscribe()
        await nc.close()