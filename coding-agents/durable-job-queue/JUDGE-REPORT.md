# Judge report — Durable Local Job Queue

Independent evaluation of the deliverable produced by the local coder
(`qwen3.8-27b-mtp-dflash2-lucebox` on ds-harness, Lucebox backend with patch
#665). Full task in `TASK.md`, execution context in `MANIFEST.yaml`.

Repository judged: `qwen38-durable-job-queue-benchmark`, branch
`bench/qwen38-durable-job-queue`, HEAD `9c04073`.

## Verdict

**PASS with two defects**, one of them substantive.

The system is correct on exactly the points the task set out to stress — lease
ownership, stale-worker safety, concurrent idempotency, backoff, packaging —
and it survives 17 adversarial tests I wrote against the specification without
looking at its own suite. The substantive defect is not in the code but in the
**divergence between what `DECISIONS.md` asserts and what the code does** in
one specific scenario (crash loop), which is precisely the class of problem
§46 asks the judge to look for.

It is not a `FAIL` because the divergent scenario produces neither corruption
nor job loss, and everything else holds. It is not a clean `PASS` because
architectural decision D005 is justified by a property the system does not
have.

## Method

I did not simply re-run the candidate's suite. I:

1. read the full source (1,146 lines) before reading its tests;
2. wrote **17 independent adversarial tests** against the task text, reusing
   neither its fixtures nor its `conftest.py` (`test_adversarial.py`, included
   here);
3. inspected the Git history, in particular the commit that modifies tests;
4. verified every hash cited in the documents against the real Git object;
5. installed the package into a **fresh venv outside the tree** and checked
   that the import resolves from `site-packages`, not the working tree;
6. ran the CLI from the installed entry point, not from source.

## Metrics

| | |
|---|---|
| source | 1,146 lines, 9 modules |
| candidate tests | 1,212 lines, 13 files, **53 tests** |
| documentation | 1,045 lines (PLAN, PROGRAM_STATE, DECISIONS, README, FINAL_REPORT) |
| candidate suite | **53/53 pass** |
| judge adversarial tests | **17/17 pass** |
| commits | 6, all on a dedicated branch |
| tracked files | 32 — no `.db`, `.venv`, `__pycache__`, `egg-info` |
| hashes cited in docs | 5, **all real and verified** |
| runtime dependencies | **zero** (stdlib only) |
| external install | succeeded, import from `site-packages` |
| CLI from installed package | works |

Generation session: 87 turns, 24.8 min of server time, 51,575 tokens
generated, 48.8 tok/s mean, DFlash2 acceptance 54.2%. Context grew from 11.7k
to 75.6k tokens.

## What holds — verified, not asserted

**Lease ownership (§10, I1–I3).** The mechanism is the correct one: a random
token (`secrets.token_hex(16)`) generated per claim, checked **inside the same
UPDATE** that changes state:

```sql
UPDATE jobs SET status='completed', ...
 WHERE id = ? AND status = 'running' AND claim_token = ?
```

with `rowcount != 1 -> LeaseLost`. No SELECT-then-check-then-UPDATE window.
Test A1 (full ABA: A claims → expires → B claims → expires → D claims → A
returns with its original token) confirms rejection on both `complete()` and
`fail()`, and that the token is fresh on every claim.

**Concurrent claim (§8, T3).** 16 threads with separate connections and a
synchronization barrier: **exactly one winner**, no exceptions (A4).
`BEGIN IMMEDIATE` + `busy_timeout=5000` + WAL.

**Concurrent idempotency (§15, T11).** 16 threads with the same
`idempotency_key`: **one job** created, no exceptions (A5). Partial unique
index plus `IntegrityError` handling that re-reads the winner. And the second
enqueue's payload **does not overwrite** the first (A6) — correct, and not
obvious.

**Backoff (§13, T16).** The job is not claimable at `available_at - 0.001` and
becomes claimable at `+0.001` (A12). Formula documented and respected.

**Terminality (I4, I5).** A completed job does not become claimable again even
after 100,000 simulated seconds; `recover()` ignores it (A10). Same for `dead`
(A11).

**Persistence and restart (§7, T15).** A `running` job survives process close,
is reclaimed after expiry, and the dead worker's token is rejected (A13).

**Lease boundary (§9).** `lease_until == now` is handled **consistently**
between `claim()` and `recover()` (A3) — not a given, and exactly the kind of
inconsistency that usually goes unnoticed.

**Error isolation.** Another job's token rejected (A17); double `complete()`
rejected (A8); `complete()` on a `pending` job rejected (A16); invalid payload
writes nothing, verified by reading the DB with raw `sqlite3` (A15).

**Concurrent recovery (§18).** 8 threads alternating `recover()` and
`claim()`: no errors, never more than one owner (A14).

## Defect 1 — substantive: D005 asserts a property the code does not have

`DECISIONS.md` D005 justifies incrementing `attempts` at claim time rather
than at fail time, and does so with **three assertions**:

> "A job with `max_attempts=3` executes at most 3 times"
> "increment-at-claim **bounds total executions** even if the worker crashes mid-execution"
> "**Consequences**: a job that crashes on every attempt still reaches `dead` after `max_attempts` claims"

**All three are false on the crash path.**

`attempts` is indeed incremented at claim, but the `make_dead` decision is
computed **only** inside `JobQueue.fail()` (`queue.py:189`). The expired-lease
reclaim branch in `Repository.claim()` selects with

```sql
WHERE status = 'running' AND lease_until <= ?
```

with no comparison between `attempts` and `max_attempts`. A worker that always
dies without ever calling `fail()` leaves the job **claimable forever**.

Evidence (test A2, executed):

```text
max_attempts = 3
12 cycles of claim -> crash -> lease expiry
result: attempts = 12, status = running, still claimable
        never dead
```

The test is written to fail if the job became `dead`: it passes, so the
divergence is confirmed, not hypothesized.

**Why it matters.** This is not a cosmetic documentation defect: it is the
*justification* for the architectural decision that is invalidated. D005
explicitly rejects the increment-at-fail alternative because "a crashed worker
would never consume its attempt — bad". But under the current implementation
the crashed worker does consume the attempt **without that having any effect**,
so the advantage for which the alternative was rejected never materializes.

**Tension with task §14** ("When the permitted attempts are exhausted: status =
dead"): with `attempts` incremented at claim, after `max_attempts` claims the
attempts *are* exhausted, yet the job stays active.

**Not listed among the risks.** `FINAL_REPORT.md` §12 lists 7 residual risks —
WAL not measured, power loss, clock skew, single-writer bottleneck, no
distributed coordination, at-least-once delivery, no background reaper — but
not this one. The closest entry ("a job may be executed more than once if the
worker crashes") is about duplicate execution, not unbounded reclaim.

**Minimal fix**: add `AND attempts < max_attempts` to the reclaim branch's
SELECT, or transition to `dead` in `recover()`/`claim()` when attempts are
exhausted. But the choice is a design one: it is entirely defensible to decide
that crashes are *intentionally* distinct from reported failures — as long as
that is what the documentation says, rather than the opposite.

## Defect 2 — minor: two governance inconsistencies

**Duplicate section.** `PROGRAM_STATE.md` contains two `## Findings log`
headings (lines 36 and 58): commit `8851a03` added a new section instead of
extending the existing one. The state document therefore has two same-named
sections with different contents.

**Inconsistent dates.** Findings F1–F5 are dated `2026-07-09`, while all six
commits are from `2026-08-29`. A seven-week gap on events that occurred during
the session. This is not a fabricated hash — §35 is formally satisfied — but it
is the same class of problem: temporal evidence in the governance document that
does not match the repository.

## What I checked and is NOT a defect

**Commit `8851a03` is not test weakening.** It was the most suspicious
candidate — a commit modifying tests after the implementation exists. I
inspected it line by line: the assertions were **strengthened**, not weakened.
Before:

```python
assert c.id == r.id                    # specific ordering
```

after:

```python
assert claimed_ids == {p.id, r.id, d.id}          # + final states
assert q.get(p.id).status.value == "completed"     # + list contents
assert len(q.list()) == 3
```

The stated rationale (FIFO ordering is not part of the contract; the task
requires only atomicity and single ownership) is correct against the text of
§8, and it is recorded as F4 with an explicit citation of §36. **This is the
right way to handle a wrong test.**

**No fabricated hashes.** The 32-character hex strings in `FINAL_REPORT.md`
that an automated check flags as hashes are in fact job IDs (`uuid4().hex`)
from the CLI demo output. All 5 commit hashes actually cited exist in the
repository.

**`JobStatus.FAILED` never persisted** is a divergence from task §5, but it is
**declared** in three places (enum docstring, D005, README) with the rationale:
a failure with retries left re-pends the job in the same transaction, so no row
is ever stored as `failed`. An explicit divergence, not a hidden one.

**No committed artifacts**: 32 tracked files, no `.db`, `.venv`,
`__pycache__`, `egg-info`. Clean working tree at the end.

## Comparison with the previous benchmark

The two benchmarks **are not comparable as scores** — the first was a
high-fidelity port, this is greenfield — but the difference in discipline is
clear:

| | compaction (port) | job queue (greenfield) |
|---|---|---|
| package importable as shipped | no (`ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX`) | **yes**, verified from external venv |
| behavioural divergences from source | 3 confirmed | n/a (no source) |
| PLAN states what the code does | **no** (5 nonexistent items) | yes, except D005 |
| tests modified after implementation | — | 1, **strengthened**, with rationale |
| governance | serious problems | present, 2 minor inconsistencies |

The defect found here is **different in nature and subtler**: there the PLAN
declared nonexistent features; here DECISIONS declares an *emergent property*
the code does not produce. The second is harder to find because it requires
executing a specific scenario, not searching for a symbol.

## Declared limits of this judgment

This judgment carries the same limit documented elsewhere in this repository:
**a test that does not enter the critical regime proves nothing.** My 17 tests
cover the races the task names explicitly plus three I added (full ABA, crash
loop, lease boundary), but they do not cover:

- real **multi-process** contention (I used threads with separate connections);
- behaviour under `SQLITE_BUSY` with `busy_timeout` exhausted;
- real crash injection (kill -9 mid-transaction);
- power loss.

The first two are reachable with additional work; the last two are correctly
listed as `UNPROVEN` by the candidate itself.

## Summary

```text
VERIFIED  - lease ownership token-guarded, atomic, ABA-resistant
VERIFIED  - concurrent claim: exactly one winner across 16 threads
VERIFIED  - concurrent idempotency: exactly one job across 16 threads
VERIFIED  - backoff, terminality, persistence, restart, lease boundary
VERIFIED  - packaging, external import, installed CLI
VERIFIED  - no fabricated hashes, no committed artifacts
VERIFIED  - the commit that modifies tests strengthens them, not weakens them

FALSIFIED - D005: "increment-at-claim bounds total executions" and
            "a job that crashes on every attempt still reaches dead"
            Evidence: 12 claims with max_attempts=3 -> attempts=12, never dead

DEFECT    - PROGRAM_STATE.md: duplicate "Findings log" section
DEFECT    - finding dates (2026-07-09) inconsistent with commits (2026-08-29)

UNPROVEN  - multi-process contention, saturated SQLITE_BUSY, crash injection,
            power loss
```
