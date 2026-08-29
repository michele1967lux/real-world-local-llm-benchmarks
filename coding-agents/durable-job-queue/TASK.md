# CODING BENCHMARK TASK — Durable Local Job Queue

> Testo integrale del task consegnato al coder, riprodotto verbatim.
> Contesto di esecuzione e criteri di valutazione: vedi `CONTEXT.md`.

## Difficulty

**Medium**

## Objective

Build from scratch a production-quality **durable local job queue** backed by SQLite.

There is no existing implementation to port.

You must design the architecture, persistence model, concurrency rules, public API, CLI, tests and documentation.

The benchmark evaluates:

* architecture;
* correctness;
* concurrency reasoning;
* failure handling;
* test quality;
* Git discipline;
* governance accuracy;
* ability to distinguish VERIFIED facts from assumptions.

A large amount of code or a large number of tests does not imply success.

---

# 1. Product goal

Create a local job queue capable of:

```text
client
  |
  +--> enqueue job
  |
  v
SQLite durable queue
  |
  +--> worker A
  |
  +--> worker B
  |
  v
claim -> execute -> complete / retry / dead
```

Jobs must survive process termination and restart.

Multiple workers must be able to operate concurrently without executing the same lease simultaneously.

---

# 2. Technology constraints

Use:

```text
Python 3.12+
SQLite
standard library where practical
```

A small, justified dependency is allowed, but unnecessary framework dependencies are discouraged.

Do not use:

```text
Redis
PostgreSQL
RabbitMQ
Celery
external queue services
Docker as a runtime requirement
```

The system must work locally with only the package and its SQLite database.

---

# 3. Required package

Create a new repository/package named conceptually:

```text
durable-job-queue
```

The exact Python import name may be chosen by you.

The package must be installable/importable from another project.

A valid external consumer must be able to do something equivalent to:

```python
from durable_job_queue import JobQueue

queue = JobQueue("jobs.db")

job = queue.enqueue(
    job_type="resize-image",
    payload={"file": "photo.jpg"},
)

print(job.id)
```

---

# 4. Job model

Every job must contain at least:

```text
id
job_type
payload
status
created_at
updated_at
attempts
max_attempts
available_at
claimed_at
lease_until
worker_id
last_error
idempotency_key
```

You may add fields when justified.

---

# 5. Job states

At minimum:

```text
pending
running
completed
failed
dead
```

Define precisely what each state means.

Document all valid state transitions.

Invalid state transitions must not silently succeed.

---

# 6. Enqueue

Required API behavior:

```python
queue.enqueue(
    job_type="email",
    payload={"to": "user@example.com"},
)
```

must durably create a job.

The returned object must contain the persistent job ID.

Payload serialization must be deterministic enough for storage and recovery.

Invalid/unserializable payloads must produce a controlled error.

---

# 7. Persistence

SQLite is the source of truth.

After:

```text
enqueue job
terminate process
restart process
```

the job must still exist with the correct state and payload.

Do not rely on process memory for correctness.

---

# 8. Claiming jobs

Workers request jobs from the queue.

Conceptually:

```python
job = queue.claim(
    worker_id="worker-1",
    lease_seconds=30,
)
```

The claim operation must be atomic.

If two workers attempt to claim the same pending job concurrently:

```text
only one worker may obtain that lease
```

A claimed job becomes:

```text
running
```

and receives a finite lease.

---

# 9. Lease semantics

A running job must have:

```text
worker_id
lease_until
```

A worker owns the job only while its lease is valid.

If the worker crashes and the lease expires:

```text
another worker must eventually be able to recover and claim the job
```

The design must prevent two valid workers from simultaneously believing they own the same current lease.

---

# 10. Stale-worker safety

This is a critical correctness requirement.

Consider:

```text
T0: Worker A claims Job X
T1: A stops responding
T2: A's lease expires
T3: Worker B claims Job X
T4: Worker A returns late
T5: Worker A tries to mark X completed
```

Worker A must **not** be able to corrupt or complete Worker B's current execution.

Design a mechanism that proves ownership of the current claim.

Do not rely only on:

```text
worker_id
```

unless you can prove that it is sufficient.

The judge will specifically test this race.

---

# 11. Completion

A worker with a valid current claim must be able to:

```python
queue.complete(...)
```

The job becomes:

```text
completed
```

Completion must be atomic.

A stale or invalid lease must fail safely.

---

# 12. Failure

A worker may report execution failure.

Conceptually:

```python
queue.fail(..., error="connection timeout")
```

The system must:

1. increment the attempt count;
2. record the failure;
3. decide whether to retry;
4. schedule retry according to the backoff policy;
5. move permanently exhausted jobs to `dead`.

---

# 13. Retry policy

Use deterministic exponential backoff.

Minimum required behavior:

```text
attempt 1 -> retry after 1 second
attempt 2 -> retry after 2 seconds
attempt 3 -> retry after 4 seconds
attempt 4 -> retry after 8 seconds
...
```

You may cap the delay.

Document the formula.

Jobs waiting for retry must not be claimable before:

```text
available_at
```

---

# 14. Maximum attempts

Every job must support:

```text
max_attempts
```

When the permitted attempts are exhausted:

```text
status = dead
```

A dead job must not be returned by normal claim operations.

---

# 15. Idempotent enqueue

Support an optional:

```text
idempotency_key
```

Example:

```python
queue.enqueue(
    job_type="invoice",
    payload={"invoice_id": 123},
    idempotency_key="invoice-123",
)
```

Repeating the same logical enqueue using the same idempotency key must not create multiple independent jobs.

Define and document the uniqueness scope.

The operation must remain correct under concurrent enqueue attempts.

---

# 16. Job lookup

Provide API(s) to retrieve a job by ID.

Example:

```python
queue.get(job_id)
```

The returned representation must expose current state and relevant metadata.

---

# 17. Job listing

Provide basic filtering such as:

```python
queue.list(status="pending")
queue.list(status="running")
queue.list(status="dead")
```

Do not turn this into a query language.

---

# 18. Recovery

The system must recover expired leases.

This may happen:

```text
during claim
through an explicit recovery operation
or another clearly documented mechanism
```

But it must not depend on a permanently running background scheduler.

Recovery semantics must be deterministic and testable.

---

# 19. CLI

Provide a usable CLI.

At minimum:

```bash
jobq enqueue --type TYPE --payload JSON
jobq list
jobq status JOB_ID
jobq worker
```

The exact CLI structure may vary.

`jobq worker` must be capable of demonstrating real job processing.

Do not build a large plugin framework.

A small built-in/demo handler registry is sufficient for the benchmark.

---

# 20. Example worker

Include at least one real example handler.

For example:

```text
echo
sleep
write-file
```

The purpose is to demonstrate end-to-end operation, not to create an application framework.

---

# 21. Time handling

Time-sensitive behavior must be testable.

Do not scatter direct calls to wall-clock time throughout the implementation if this makes tests depend on sleeping for many seconds.

Prefer a clear clock/time seam where appropriate.

Tests should not need long real sleeps to verify retry and lease expiration semantics.

---

# 22. Concurrency

SQLite access must be designed intentionally.

Document:

```text
transaction boundaries
locking assumptions
busy timeout / retry behavior if used
claim transaction
idempotency transaction
completion/failure transaction
```

Do not rely on "SQLite probably serializes it" as the concurrency design.

---

# 23. Error model

Define controlled exceptions/errors for important cases.

Examples:

```text
JobNotFound
InvalidStateTransition
LeaseLost
InvalidPayload
QueueConfigurationError
```

Names may differ.

Do not expose arbitrary SQLite exceptions for expected domain failures unless explicitly justified.

---

# 24. Public API

Keep the public surface small.

A reasonable shape might contain:

```text
JobQueue
Job
JobStatus
domain exceptions
```

Do not expose internal SQLite repository details unnecessarily.

---

# 25. Packaging

The package must be installable.

At minimum:

```bash
pip install -e .
```

must work.

And from outside the repository tree:

```python
import durable_job_queue
```

must work.

The CLI entry point must also be installed through package metadata.

---

# 26. Required behavioral tests

At minimum implement and execute the following.

## T1 — persistence

```text
enqueue
close queue/process
reopen
job still exists
```

## T2 — basic claim

A pending available job can be claimed.

## T3 — concurrent claim

Two queue/worker instances compete for one job.

Exactly one obtains it.

## T4 — valid completion

Current lease owner completes successfully.

## T5 — stale completion

Worker A loses lease.

Worker B reclaims.

Worker A then attempts completion.

Expected:

```text
A is rejected
B remains authoritative
```

## T6 — expired lease recovery

Expired running job becomes claimable again.

## T7 — retry attempt 1

Failure schedules retry at the expected future availability.

## T8 — retry progression

Verify:

```text
1s
2s
4s
8s
```

or your documented equivalent.

## T9 — dead transition

Exhausted job becomes dead and is not normally claimable.

## T10 — idempotent enqueue

Sequential duplicate idempotency key produces one job.

## T11 — concurrent idempotent enqueue

Concurrent enqueue attempts using the same idempotency key still result in one durable logical job.

## T12 — different idempotency keys

Produce distinct jobs.

## T13 — invalid payload

Controlled error; database unchanged.

## T14 — invalid state transition

Example:

```text
complete pending job
```

must not silently succeed.

## T15 — restart during running job

Persisted running job + expired lease must recover correctly after restart.

## T16 — future retry is not claimable

Job cannot be claimed before `available_at`.

## T17 — public external consumer

Install package and use public API from outside the repository.

## T18 — CLI smoke test

Enqueue/list/status path works through installed CLI.

---

# 27. Additional tests

You are expected to identify additional important cases yourself.

The specification intentionally does not enumerate every possible race or invariant.

The quality of additional tests will be evaluated.

Do not add tests merely to increase the count.

---

# 28. GOVERNANCE — mandatory

Governance compliance is part of the benchmark.

A functionally correct queue can still receive a poor score if repository state or evidence is unreliable.

---

# 29. Repository initialization

Begin from an empty/new repository.

Before implementation:

```bash
git init
git status --short
git branch --show-current
git rev-parse HEAD
```

If there is no first commit yet, record that fact truthfully.

Create a primary development branch.

Recommended:

```text
bench/qwen38-durable-job-queue
```

Do not implement directly on an accidental default branch without documenting the decision.

---

# 30. Initial governance files

Before production implementation, create:

```text
PLAN.md
PROGRAM_STATE.md
DECISIONS.md
```

Commit these before implementing the queue.

---

# 31. PLAN.md

Before production code exists, `PLAN.md` must define:

```text
goal
scope
non-goals
proposed architecture
SQLite schema proposal
state machine
lease strategy
transaction strategy
idempotency strategy
retry strategy
test strategy
known risks
uncertainties
```

It is acceptable for the plan to later prove wrong.

It is not acceptable to rewrite history and pretend the original plan predicted everything.

When a material assumption changes, record the divergence.

---

# 32. PROGRAM_STATE.md

Maintain the factual state of the project.

Every important claim must be classified as:

```text
VERIFIED
CHARACTERIZED
INFERRED
UNPROVEN
```

Examples:

```text
VERIFIED:
concurrent claim test proves one lease owner

INFERRED:
WAL mode may improve concurrency

UNPROVEN:
behavior under abrupt OS power loss
```

Do not call something VERIFIED because code exists.

Verification requires executed evidence.

---

# 33. DECISIONS.md

Record material architectural decisions.

Use stable IDs.

For example:

```text
D001 — SQLite persistence model
D002 — lease ownership mechanism
D003 — claim transaction
D004 — idempotency scope
D005 — retry backoff
```

Each decision should include:

```text
context
decision
alternatives considered
reason
consequences
status
```

Do not fabricate Git hashes.

---

# 34. Git history requirements

Use coherent commits.

A suggested structure is:

```text
docs: establish architecture and governance
test: define core queue behavioral contract
feat: implement persistent queue core
feat: implement leases and recovery
feat: implement retry and dead jobs
feat: implement idempotent enqueue
feat: add CLI and demo worker
test: add concurrency and stale-worker regressions
docs: finalize evidence and usage
```

The exact structure may differ.

Requirements:

```text
no giant unexplained final commit
no destructive rewriting to hide mistakes
truthful commit messages
one coherent concern per commit where practical
```

---

# 35. Never invent commit hashes

A commit cannot know its own future hash.

Do not place invented hashes in:

```text
PROGRAM_STATE.md
DECISIONS.md
PLAN.md
FINAL_REPORT.md
```

Reference only commits that already exist.

If necessary write:

```text
PENDING
```

and record the actual hash in a later commit.

Fabricated commit evidence is a benchmark failure.

---

# 36. Preserve evidence

If a test exposes a bug:

```text
do not immediately rewrite the test to match the implementation
```

First determine whether:

```text
the implementation is wrong
the test is wrong
the specification is ambiguous
```

Record the finding.

---

# 37. No test weakening

Forbidden without explicit evidence:

```text
deleting failing tests
adding skip/xfail to obtain green
weakening assertions
mocking away SQLite/concurrency behavior under evaluation
replacing actual integration tests with fake repositories
```

---

# 38. Stop conditions

Stop implementation and record a finding before proceeding if:

1. two consecutive defects arise from the same root-cause class;
2. an architectural assumption marked VERIFIED is contradicted;
3. a core state-machine invariant proves false;
4. fixing a defect requires redesigning a previously committed architectural boundary;
5. tests expose possible durable-state corruption;
6. Git state unexpectedly contains work that is not yours.

When a stop condition occurs:

```text
update PROGRAM_STATE.md
update PLAN.md if necessary
commit/document the new evidence
then resume only with a revised plan
```

Do not silently route around it.

---

# 39. Required invariants

At minimum reason about and test these invariants.

## I1

At most one current lease exists for a job.

## I2

Only the owner of the current valid lease may complete/fail it.

## I3

A stale worker cannot overwrite state produced by a newer claim.

## I4

A completed job never returns to pending/running.

## I5

A dead job is not normally claimable.

## I6

A job scheduled for future retry is not claimable early.

## I7

One idempotency key identifies at most one logical job in its defined scope.

## I8

Committed state survives reopening the database.

Add any additional invariants you discover.

---

# 40. Real runtime demonstration

Before completion, execute a real demonstration.

Example:

```text
1. create database
2. enqueue jobs
3. start two workers
4. show distinct claims
5. intentionally terminate one worker
6. wait/advance until lease expiry
7. recover its job with another worker
8. complete it
9. restart queue process
10. prove persisted final state
```

Capture the commands and meaningful output in the final report.

---

# 41. Required validation

Before declaring PASS:

```bash
pytest
```

plus:

```text
type/static checks if configured
package build
editable/fresh install
external import test
CLI smoke test
concurrency tests
```

Use the actual commands appropriate to the project you created.

---

# 42. Final repository inspection

Run and record:

```bash
git status --short
git log --oneline --decorate --graph
git diff <baseline>...HEAD
```

Because this is greenfield, use the first governance/baseline commit as the reference where appropriate.

Verify:

```text
no temporary DBs committed unintentionally
no test artifacts committed accidentally
no secrets
no unrelated files
```

---

# 43. README.md

Provide end-user documentation covering:

```text
installation
quick start
public API
CLI
job lifecycle
lease semantics
retry semantics
idempotency
SQLite file location
limitations
```

Do not claim guarantees that were not tested or designed.

---

# 44. FINAL_REPORT.md

At completion create:

```text
FINAL_REPORT.md
```

with exactly these sections.

## 1. Verdict

```text
PASS
PARTIAL
FAIL
```

Explain why.

## 2. Architecture

Final component structure.

## 3. State machine

Actual implemented transitions.

## 4. Persistence model

Schema and transaction boundaries.

## 5. Lease correctness

How stale workers are prevented from committing.

## 6. Retry behavior

Backoff and dead transition.

## 7. Idempotency

Definition and concurrency behavior.

## 8. Test evidence

List executed tests/commands and results.

## 9. Runtime demonstration

Observed end-to-end execution.

## 10. Git evidence

Branch and commit history.

## 11. Divergences from original plan

Every material architecture/design change.

## 12. Remaining risks

Anything not fully proven.

Do not write "none" by default.

---

# 45. Acceptance criteria

The benchmark is successful only if:

```text
[ ] greenfield project created
[ ] package installable
[ ] public API importable externally
[ ] SQLite persistence works
[ ] concurrent claim is safe
[ ] finite leases implemented
[ ] expired leases recoverable
[ ] stale worker cannot commit
[ ] retries work
[ ] exponential backoff tested
[ ] dead jobs implemented
[ ] idempotent enqueue works sequentially
[ ] idempotent enqueue works concurrently
[ ] CLI works
[ ] real worker demonstration completed
[ ] T1-T18 executed successfully
[ ] important additional edge cases tested
[ ] PLAN committed before implementation
[ ] PROGRAM_STATE maintained truthfully
[ ] DECISIONS maintained
[ ] Git history coherent
[ ] no invented commit hashes
[ ] no weakened tests
[ ] FINAL_REPORT matches repository reality
```

---

# 46. Benchmark evaluation note

This project will later be judged independently.

The judge may create tests that were not included in your suite.

The judge will not trust:

```text
test count
self-assessment
documentation claims
comments
PROGRAM_STATE claims
```

without runtime or repository evidence.

The independent judge will specifically look for:

```text
lease races
stale-worker completion
idempotency races
transaction-boundary errors
state-machine violations
restart behavior
package/import failures
CLI/runtime discrepancies
governance inconsistencies
self-confirming tests
```

Design and verify accordingly.
