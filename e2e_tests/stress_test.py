"""Opt-in stress / resilience harness for the concurrency branch.

Drives load over NATS directly (HTTP is rate-limited to 10/min per endpoint in
the Flask layer, so it cannot express concurrency). Every test here is marked
``@pytest.mark.stress`` only — never ``@pytest.mark.e2e`` — so the default
container CMD ``pytest -m e2e`` skips them. Run explicitly with::

    pytest -m stress -v -s

Knobs are env-overridable (see the constants below). Reports are printed with
plain ``print`` so they surface under ``pytest -s``.
"""

import os
import time
import json
import asyncio
import itertools
from collections import Counter

import pytest
import nats
from nats.errors import TimeoutError as NatsTimeoutError, NoRespondersError

NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
TEST_IMAGE = os.path.join(os.path.dirname(__file__), "fixtures", "test1.png")

CONNECTIONS = int(os.getenv("STRESS_CONNECTIONS", "10"))
SOLVE_REQUESTS = int(os.getenv("STRESS_SOLVE_REQUESTS", "200"))     # tier A
MANUAL_REQUESTS = int(os.getenv("STRESS_MANUAL_REQUESTS", "100"))   # tier B
PROCESS_REQUESTS = int(os.getenv("STRESS_PROCESS_REQUESTS", "20"))  # tier C
SOLVE_TIMEOUT = float(os.getenv("STRESS_SOLVE_TIMEOUT", "15"))
MANUAL_TIMEOUT = float(os.getenv("STRESS_MANUAL_TIMEOUT", "20"))
PROCESS_TIMEOUT = float(os.getenv("STRESS_PROCESS_TIMEOUT", "60"))
READY_DEADLINE = float(os.getenv("STRESS_READY_DEADLINE", "90"))

# Base puzzle / solution lifted from
# service_layer_rust/tests/worker_nats_api.rs (test_puzzle / expected_solution).
BASE_PUZZLE = [
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
BASE_SOLVED = [
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


def generate_puzzles(count):
    """Produce `count` distinct, solvable, conflict-free 9x9 boards.

    Each board is a digit-relabelling of the complete BASE_SOLVED grid,
    projected onto the givens mask of BASE_PUZZLE. A relabel of a valid full
    grid is itself valid, so blanking the non-given cells yields a puzzle whose
    relabeled completion is a solution -> always solvable, givens always
    conflict-free. Distinct projections vastly exceed the defaults (<=200), so
    the `raise` is never hit at default knobs.
    """
    out, seen = [], set()
    for perm in itertools.permutations("123456789"):
        dmap = {str(i + 1): perm[i] for i in range(9)}
        board = [
            [dmap[BASE_SOLVED[r][c]] if BASE_PUZZLE[r][c] != "." else "."
             for c in range(9)]
            for r in range(9)
        ]
        key = tuple(tuple(row) for row in board)
        if key in seen:
            continue
        seen.add(key)
        out.append(board)
        if len(out) == count:
            return out
    raise RuntimeError(f"only generated {len(out)} distinct puzzles, need {count}")


def pct(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(p / 100.0 * len(s)))]


async def _drive(conns, n, timeout, build_payload, headers, subject, validate):
    """Fan `n` request/reply calls out concurrently, round-robin over conns.

    Returns a list of (latency, outcome) tuples. Outcome is "ok" or a failure
    class: timeout / no_responders / error / bad_result / exc:<repr>.
    """
    async def one(i):
        nc = conns[i % len(conns)]
        t0 = time.monotonic()
        try:
            msg = await nc.request(
                subject, build_payload(i), timeout=timeout,
                headers=headers(i) if headers else None,
            )
            dt = time.monotonic() - t0
            return dt, validate(json.loads(msg.data.decode()))
        except NoRespondersError:
            return time.monotonic() - t0, "no_responders"
        except NatsTimeoutError:
            return time.monotonic() - t0, "timeout"
        except Exception as e:  # noqa: BLE001
            return time.monotonic() - t0, f"exc:{e!r}"

    return await asyncio.gather(*[one(i) for i in range(n)])


def _validate_solve(r):
    if (r.get("is_solved") is True
            and len(r.get("board", [])) == 9
            and all("." not in row for row in r["board"])):
        return "ok"
    return "bad_result"


def _validate_service(r):
    if "error" in r:
        return "error"
    if (len(r.get("solved_board", [])) == 9
            and all("." not in row for row in r["solved_board"])):
        return "ok"
    return "bad_result"


def _report(tier, results, wall_time):
    latencies = [dt for dt, _ in results]
    outcomes = [o for _, o in results]
    total = len(results)
    ok = sum(1 for o in outcomes if o == "ok")
    failures = Counter(o for o in outcomes if o != "ok")
    success_rate = ok / total if total else 0.0
    throughput = total / wall_time if wall_time else 0.0
    parallelism = (sum(latencies) / wall_time) if wall_time else 0.0
    print(f"\n===== STRESS REPORT: {tier} =====")
    print(f"  total            : {total}")
    print(f"  ok               : {ok}")
    print(f"  success_rate     : {success_rate:.4f}")
    print(f"  failures         : {dict(failures)}")
    print(f"  latency p50      : {pct(latencies, 50):.4f}s")
    print(f"  latency p95      : {pct(latencies, 95):.4f}s")
    print(f"  latency p99      : {pct(latencies, 99):.4f}s")
    print(f"  latency max      : {max(latencies) if latencies else 0.0:.4f}s")
    print(f"  wall_time        : {wall_time:.4f}s")
    print(f"  throughput       : {throughput:.2f} req/s")
    print(f"  parallelism_fact : {parallelism:.2f}x  (sum(lat)/wall; >1 == overlap)")
    print("=================================")
    return {
        "total": total, "ok": ok, "success_rate": success_rate,
        "failures": failures, "latencies": latencies,
    }


async def _await_ready(nc):
    """Block until ping has a responder and a solve round-trips, or deadline."""
    deadline = time.monotonic() + READY_DEADLINE
    probe = json.dumps({"is_solved": False, "k": 3, "n": 3,
                        "board": generate_puzzles(1)[0]}).encode()
    ping_ok = solve_ok = False
    while time.monotonic() < deadline:
        try:
            if not ping_ok:
                await nc.request("sudoku.ping", b"", timeout=1.0)
                ping_ok = True
            if not solve_ok:
                await nc.request("sudoku.solve", probe, timeout=5.0)
                solve_ok = True
            if ping_ok and solve_ok:
                return
        except Exception:
            await asyncio.sleep(2)
    raise RuntimeError("pipeline not ready within deadline")


async def _open_pool():
    return [await nats.connect(NATS_URL) for _ in range(CONNECTIONS)]


async def _close_pool(conns):
    for nc in conns:
        try:
            await nc.close()
        except Exception:
            pass


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.stress
def test_stress_solver_direct():
    """Tier A: hammer the solver worker directly via sudoku.solve.

    No cache sits in front of the worker, so every distinct board reaches the
    solver. This is the purest measure of the per-message tokio::spawn
    concurrency this branch introduced.
    """
    boards = generate_puzzles(SOLVE_REQUESTS)

    def build(i):
        return json.dumps({"is_solved": False, "k": 3, "n": 3,
                           "board": boards[i]}).encode()

    async def run():
        conns = await _open_pool()
        try:
            await _await_ready(conns[0])
            t0 = time.monotonic()
            results = await _drive(conns, SOLVE_REQUESTS, SOLVE_TIMEOUT,
                                   build, None, "sudoku.solve", _validate_solve)
            return results, time.monotonic() - t0
        finally:
            await _close_pool(conns)

    results, wall = _run(run())
    m = _report("tier A: sudoku.solve (worker direct)", results, wall)
    no_resp = sum(1 for _, o in results if o == "no_responders")
    assert no_resp == 0, f"{no_resp} no_responders (worker dropped requests)"
    assert m["success_rate"] >= 0.99, f"success_rate {m['success_rate']:.4f} < 0.99"
    assert pct(m["latencies"], 99) < SOLVE_TIMEOUT


@pytest.mark.stress
def test_stress_service_manual():
    """Tier B: hammer the service layer via sudoku.manual_solve.

    Boards are distinct, so each is a cache miss -> solver call -> DB insert.
    This exercises the SQLite busy_timeout path under concurrent writes.
    """
    boards = generate_puzzles(MANUAL_REQUESTS)

    def build(i):
        return json.dumps({"k": 3, "n": 3, "board": boards[i]}).encode()

    async def run():
        conns = await _open_pool()
        try:
            await _await_ready(conns[0])
            t0 = time.monotonic()
            results = await _drive(conns, MANUAL_REQUESTS, MANUAL_TIMEOUT,
                                   build, None, "sudoku.manual_solve",
                                   _validate_service)
            return results, time.monotonic() - t0
        finally:
            await _close_pool(conns)

    results, wall = _run(run())
    m = _report("tier B: sudoku.manual_solve (cache-miss + DB write)", results, wall)
    no_resp = sum(1 for _, o in results if o == "no_responders")
    assert no_resp == 0, f"{no_resp} no_responders (service dropped requests)"
    assert m["success_rate"] >= 0.99, f"success_rate {m['success_rate']:.4f} < 0.99"
    assert pct(m["latencies"], 99) < MANUAL_TIMEOUT


@pytest.mark.stress
def test_stress_full_pipeline():
    """Tier C: end-to-end via sudoku.process with a fixed image.

    All requests reuse one image, so OCR (serial, unchanged by this branch) is
    the limiter and the solver mostly cache-hits. This tier proves end-to-end
    liveness under load, not solver parallelism.
    """
    with open(TEST_IMAGE, "rb") as f:
        image_bytes = f.read()

    def build(_i):
        return image_bytes

    def hdrs(_i):
        return {"n": "3", "k": "3"}

    async def run():
        conns = await _open_pool()
        try:
            await _await_ready(conns[0])
            t0 = time.monotonic()
            results = await _drive(conns, PROCESS_REQUESTS, PROCESS_TIMEOUT,
                                   build, hdrs, "sudoku.process",
                                   _validate_service)
            return results, time.monotonic() - t0
        finally:
            await _close_pool(conns)

    results, wall = _run(run())
    m = _report("tier C: sudoku.process (full pipeline, fixed image)", results, wall)
    no_resp = sum(1 for _, o in results if o == "no_responders")
    assert no_resp == 0, f"{no_resp} no_responders (pipeline dropped requests)"
    assert m["success_rate"] >= 0.95, f"success_rate {m['success_rate']:.4f} < 0.95"
    assert pct(m["latencies"], 99) < PROCESS_TIMEOUT


@pytest.mark.stress
def test_stress_worker_survives_malformed_payload():
    """Resilience: malformed sudoku.solve payloads must not wedge the worker.

    A malformed message hits the deserialize-error path, which now `return`s
    inside the spawned task (no reply), so the requester times out. We fire
    those concurrently with valid work, then prove the worker still serves a
    fresh valid request afterwards. The publish/serialize ?-> explicit-handling
    hardening is not externally triggerable and is covered by build + review,
    not this probe.
    """
    valid_boards = generate_puzzles(50)

    def build_valid(i):
        return json.dumps({"is_solved": False, "k": 3, "n": 3,
                           "board": valid_boards[i]}).encode()

    async def run():
        conns = await _open_pool()
        try:
            await _await_ready(conns[0])

            async def malformed(i):
                nc = conns[i % len(conns)]
                try:
                    await nc.request("sudoku.solve", b"\x00 not valid json",
                                     timeout=3.0)
                    return "unexpected_reply"
                except NatsTimeoutError:
                    return "timeout_expected"
                except Exception as e:  # noqa: BLE001
                    return f"exc:{e!r}"

            t0 = time.monotonic()
            valid_task = _drive(conns, 50, SOLVE_TIMEOUT, build_valid, None,
                                "sudoku.solve", _validate_solve)
            bad_task = asyncio.gather(*[malformed(i) for i in range(10)])
            valid_results, bad_results = await asyncio.gather(valid_task, bad_task)
            wall = time.monotonic() - t0

            # Worker still alive and serving after the malformed barrage.
            probe = json.dumps({"is_solved": False, "k": 3, "n": 3,
                                "board": generate_puzzles(1)[0]}).encode()
            after = await conns[0].request("sudoku.solve", probe,
                                           timeout=SOLVE_TIMEOUT)
            after_json = json.loads(after.data.decode())
            return valid_results, bad_results, after_json, wall
        finally:
            await _close_pool(conns)

    valid_results, bad_results, after_json, wall = _run(run())
    m = _report("resilience: malformed sudoku.solve under load", valid_results, wall)
    print(f"  malformed outcomes: {dict(Counter(bad_results))}")
    print(f"  post-injection probe is_solved: {after_json.get('is_solved')}")

    assert after_json.get("is_solved") is True, (
        "worker did not solve a fresh request after malformed barrage"
    )
    no_resp = sum(1 for _, o in valid_results if o == "no_responders")
    assert no_resp == 0, f"{no_resp} no_responders in valid batch"
    assert m["success_rate"] >= 0.95, f"success_rate {m['success_rate']:.4f} < 0.95"
