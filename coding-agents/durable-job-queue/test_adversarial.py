"""Independent adversarial tests for durable-job-queue.

Written by the judge against the TASK specification, not against the
candidate's implementation or its test suite. No fixtures are reused from
the candidate's conftest.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from durable_job_queue import JobQueue
from durable_job_queue.errors import InvalidStateTransition, LeaseLost


class FakeClock:
    def __init__(self, t: float = 1_000_000.0) -> None:
        self.t = t

    def now(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def q(tmp_path: Path, clock=None, name="jobs.db") -> JobQueue:
    return JobQueue(str(tmp_path / name), clock=clock)


# ---------------------------------------------------------------- A1: ABA
def test_A1_aba_stale_token_rejected_after_full_reclaim_cycle(tmp_path):
    """A's token must stay invalid even after B claims, completes-fails, and
    a third claim happens. Token must be fresh per claim."""
    c = FakeClock()
    queue = q(tmp_path, c)
    job = queue.enqueue("t", {"n": 1}, max_attempts=10)

    a = queue.claim("A", lease_seconds=10)
    token_a = a.token
    c.advance(11)                       # A's lease expires
    b = queue.claim("B", lease_seconds=10)
    assert b.id == job.id
    assert b.token != token_a, "claim token must be fresh per claim"
    c.advance(11)                       # B's lease expires too
    d = queue.claim("D", lease_seconds=10)
    assert d.token not in (token_a, b.token)

    # A returns very late with its original token
    with pytest.raises(LeaseLost):
        queue.complete(job.id, token=token_a)
    with pytest.raises(LeaseLost):
        queue.fail(job.id, token=token_a, error="late")
    assert queue.get(job.id).status.value == "running"
    queue.close()


# ------------------------------------------------- A2: immortal reclaim
def test_A2_crash_loop_never_reaches_dead(tmp_path):
    """A worker that always crashes (never calls fail) reclaims forever.

    attempts is incremented at claim time, so it passes max_attempts, yet
    the job stays claimable and never becomes dead.
    """
    c = FakeClock()
    queue = q(tmp_path, c)
    job = queue.enqueue("t", {"n": 1}, max_attempts=3)

    for _ in range(12):
        got = queue.claim("crasher", lease_seconds=5)
        assert got is not None, "job stopped being claimable"
        c.advance(6)                    # worker dies, lease expires

    final = queue.get(job.id)
    queue.close()
    assert final.attempts > final.max_attempts, (
        f"attempts={final.attempts} max={final.max_attempts}")
    assert final.status.value != "dead", (
        "spec §14: attempts exhausted should become dead; "
        f"got status={final.status.value} attempts={final.attempts}")


# ------------------------------------------- A3: lease boundary equality
def test_A3_lease_boundary_exact_equality(tmp_path):
    """lease_until == now: is the lease expired or still owned?

    Whatever the choice, it must be consistent between claim() and recover().
    """
    c = FakeClock()
    queue = q(tmp_path, c)
    queue.enqueue("t", {}, max_attempts=5)
    a = queue.claim("A", lease_seconds=10)
    lease_until = a.lease_until

    c.t = lease_until                   # exactly at the boundary
    reclaimed = queue.claim("B", lease_seconds=10)
    claim_says_expired = reclaimed is not None

    queue2 = q(tmp_path, FakeClock(lease_until), name="jobs.db")
    # fresh state for recover(): redo on a second db
    c2 = FakeClock()
    q2 = q(tmp_path, c2, name="jobs2.db")
    q2.enqueue("t", {}, max_attempts=5)
    a2 = q2.claim("A", lease_seconds=10)
    c2.t = a2.lease_until
    recover_says_expired = q2.recover() == 1

    queue.close(); queue2.close(); q2.close()
    assert claim_says_expired == recover_says_expired, (
        f"inconsistent boundary: claim={claim_says_expired} "
        f"recover={recover_says_expired}")


# ------------------------------------------------ A4: concurrent claim
def test_A4_concurrent_claim_single_owner(tmp_path):
    db = str(tmp_path / "jobs.db")
    setup = JobQueue(db)
    job = setup.enqueue("t", {"n": 1}, max_attempts=99)
    setup.close()

    N = 16
    results: list = []
    lock = threading.Lock()
    barrier = threading.Barrier(N)

    def worker(i: int) -> None:
        qq = JobQueue(db)
        barrier.wait()
        try:
            got = qq.claim(f"w{i}", lease_seconds=60)
        except Exception as e:                      # noqa: BLE001
            got = e
        with lock:
            results.append(got)
        qq.close()

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in ts: t.start()
    for t in ts: t.join()

    errors = [r for r in results if isinstance(r, Exception)]
    winners = [r for r in results if r is not None and not isinstance(r, Exception)]
    assert not errors, f"claim raised under contention: {errors[:3]}"
    assert len(winners) == 1, f"expected exactly 1 winner, got {len(winners)}"
    assert winners[0].id == job.id
    tokens = {w.token for w in winners}
    assert len(tokens) == 1


# ------------------------------- A5: concurrent idempotent enqueue
def test_A5_concurrent_idempotent_enqueue_single_job(tmp_path):
    db = str(tmp_path / "jobs.db")
    JobQueue(db).close()

    N = 16
    results: list = []
    lock = threading.Lock()
    barrier = threading.Barrier(N)

    def worker(i: int) -> None:
        qq = JobQueue(db)
        barrier.wait()
        try:
            j = qq.enqueue("invoice", {"i": 1}, idempotency_key="inv-1")
        except Exception as e:                      # noqa: BLE001
            j = e
        with lock:
            results.append(j)
        qq.close()

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in ts: t.start()
    for t in ts: t.join()

    errors = [r for r in results if isinstance(r, Exception)]
    assert not errors, f"concurrent enqueue raised: {errors[:3]}"
    ids = {r.id for r in results}
    assert len(ids) == 1, f"expected one logical job, got {len(ids)}"

    check = JobQueue(db)
    assert len(check.list()) == 1
    check.close()


# --------------------------- A6: same key, different payload
def test_A6_same_key_different_payload(tmp_path):
    queue = q(tmp_path)
    a = queue.enqueue("invoice", {"v": 1}, idempotency_key="k")
    b = queue.enqueue("invoice", {"v": 2}, idempotency_key="k")
    stored = queue.get(b.id)
    queue.close()
    assert a.id == b.id, "same key must map to one logical job"
    # The second payload must NOT silently overwrite the first.
    assert stored.payload == {"v": 1}, (
        f"payload changed under the same idempotency key: {stored.payload}")


# --------------------------- A7: same key, different job_type
def test_A7_same_key_different_job_type(tmp_path):
    queue = q(tmp_path)
    a = queue.enqueue("invoice", {"v": 1}, idempotency_key="k")
    b = queue.enqueue("email", {"v": 1}, idempotency_key="k")
    queue.close()
    # Scope is documented as global; assert the documented behavior holds.
    assert a.id == b.id, "idempotency scope is documented as global by key"
    assert queue_type_of(a) == "invoice"


def queue_type_of(job):
    return job.job_type


# ------------------------------------------------ A8: complete twice
def test_A8_complete_twice(tmp_path):
    c = FakeClock()
    queue = q(tmp_path, c)
    job = queue.enqueue("t", {}, max_attempts=5)
    a = queue.claim("A", lease_seconds=30)
    queue.complete(job.id, token=a.token)
    with pytest.raises((InvalidStateTransition, LeaseLost)):
        queue.complete(job.id, token=a.token)
    assert queue.get(job.id).status.value == "completed"
    queue.close()


# ------------------------------- A9: fail after recover re-pends
def test_A9_fail_after_recovery_repended(tmp_path):
    c = FakeClock()
    queue = q(tmp_path, c)
    job = queue.enqueue("t", {}, max_attempts=5)
    a = queue.claim("A", lease_seconds=10)
    c.advance(11)
    assert queue.recover() == 1
    assert queue.get(job.id).status.value == "pending"
    with pytest.raises((LeaseLost, InvalidStateTransition)):
        queue.fail(job.id, token=a.token, error="late")
    assert queue.get(job.id).status.value == "pending"
    queue.close()


# ------------------------- A10: completed job never returns to running
def test_A10_completed_is_terminal(tmp_path):
    c = FakeClock()
    queue = q(tmp_path, c)
    job = queue.enqueue("t", {}, max_attempts=5)
    a = queue.claim("A", lease_seconds=10)
    queue.complete(job.id, token=a.token)
    c.advance(10_000)
    assert queue.recover() == 0
    assert queue.claim("B", lease_seconds=10) is None
    assert queue.get(job.id).status.value == "completed"
    queue.close()


# ------------------------------ A11: dead job not claimable, ever
def test_A11_dead_not_claimable(tmp_path):
    c = FakeClock()
    queue = q(tmp_path, c)
    job = queue.enqueue("t", {}, max_attempts=1)
    a = queue.claim("A", lease_seconds=10)
    queue.fail(job.id, token=a.token, error="boom")
    assert queue.get(job.id).status.value == "dead"
    c.advance(100_000)
    assert queue.claim("B", lease_seconds=10) is None
    assert queue.recover() == 0
    queue.close()


# ------------------------ A12: future retry not claimable early
def test_A12_backoff_not_claimable_before_available_at(tmp_path):
    c = FakeClock()
    queue = q(tmp_path, c)
    job = queue.enqueue("t", {}, max_attempts=5)
    a = queue.claim("A", lease_seconds=10)
    queue.fail(job.id, token=a.token, error="x")
    after = queue.get(job.id)
    assert after.status.value == "pending"
    delay = after.available_at - c.t
    assert delay > 0
    c.advance(delay - 0.001)
    assert queue.claim("B", lease_seconds=10) is None, "claimed before available_at"
    c.advance(0.002)
    assert queue.claim("B", lease_seconds=10) is not None
    queue.close()


# ------------------------------- A13: crash/reopen with running job
def test_A13_restart_with_running_job(tmp_path):
    db = str(tmp_path / "jobs.db")
    c = FakeClock()
    q1 = JobQueue(db, clock=c)
    job = q1.enqueue("t", {"k": "v"}, max_attempts=5)
    a = q1.claim("A", lease_seconds=10)
    q1.close()                                  # simulate process death

    c2 = FakeClock(c.t + 11)
    q2 = JobQueue(db, clock=c2)
    reread = q2.get(job.id)
    assert reread.status.value == "running"
    assert reread.payload == {"k": "v"}
    got = q2.claim("B", lease_seconds=10)
    assert got is not None and got.id == job.id
    with pytest.raises(LeaseLost):
        q2.complete(job.id, token=a.token)
    q2.close()


# ---------------------- A14: recovery concurrent with claim
def test_A14_concurrent_recover_and_claim(tmp_path):
    db = str(tmp_path / "jobs.db")
    setup = JobQueue(db)
    setup.enqueue("t", {}, max_attempts=99)
    a = setup.claim("A", lease_seconds=0.001)
    setup.close()

    import time
    time.sleep(0.05)                            # lease genuinely expired

    N = 8
    out: list = []
    lock = threading.Lock()
    barrier = threading.Barrier(N)

    def worker(i: int) -> None:
        qq = JobQueue(db)
        barrier.wait()
        try:
            r = qq.recover() if i % 2 == 0 else qq.claim(f"w{i}", 60)
        except Exception as e:                  # noqa: BLE001
            r = e
        with lock:
            out.append((i, r))
        qq.close()

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in ts: t.start()
    for t in ts: t.join()

    errors = [r for _, r in out if isinstance(r, Exception)]
    assert not errors, f"recover/claim raced into an error: {errors[:3]}"
    claims = [r for i, r in out if i % 2 == 1 and r is not None
              and not isinstance(r, Exception)]
    assert len(claims) <= 1, f"{len(claims)} concurrent owners"


# ---------------------------- A15: invalid payload leaves db untouched
def test_A15_invalid_payload_no_write(tmp_path):
    db = str(tmp_path / "jobs.db")
    queue = JobQueue(db)
    before = len(queue.list())
    for bad in ({"x": object()}, ["not", "a", "dict"], "string", 42, None):
        with pytest.raises(Exception):
            queue.enqueue("t", bad)
    assert len(queue.list()) == before
    queue.close()
    raw = sqlite3.connect(db)
    assert raw.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == before
    raw.close()


# ------------------------ A16: complete a pending job must not succeed
def test_A16_complete_pending_rejected(tmp_path):
    queue = q(tmp_path)
    job = queue.enqueue("t", {}, max_attempts=5)
    with pytest.raises((InvalidStateTransition, LeaseLost)):
        queue.complete(job.id, token="anything")
    assert queue.get(job.id).status.value == "pending"
    queue.close()


# --------------- A17: token from another job cannot complete this one
def test_A17_cross_job_token_rejected(tmp_path):
    queue = q(tmp_path)
    j1 = queue.enqueue("t", {"a": 1}, max_attempts=5)
    j2 = queue.enqueue("t", {"a": 2}, max_attempts=5)
    c1 = queue.claim("A", lease_seconds=30)
    c2 = queue.claim("B", lease_seconds=30)
    assert {c1.id, c2.id} == {j1.id, j2.id}
    with pytest.raises(LeaseLost):
        queue.complete(c1.id, token=c2.token)
    assert queue.get(c1.id).status.value == "running"
    queue.close()
