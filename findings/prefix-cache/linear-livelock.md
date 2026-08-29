# The prefix-cache livelock — root cause, upstream fix, and what is actually ours

This is the bug that cost 91% of wall-clock in a real agent session. It is
also the chapter where an uncomfortable thing has to be said plainly: **the fix
is not an original contribution of ours.**

## 1. The problem, quantified

Real ds-harness session, 91 turns analysed:

| | |
|---|---|
| turns with `prefix_len` frozen at 35328 | **62 of 91 (68%)** |
| total prefill | 4127 s |
| total decode | 1247 s |
| prefill/decode ratio | **3.31×** |
| within the frozen turns | prefill 3479 s vs decode 360 s — **91% of wall-clock in prefill** |
| prefill with a working cache, same prompt | ~3.4 s instead of ~86 s |

At that point the bottleneck was neither DFlash2 nor decode: it was the cache
frontier failing to advance.

## 2. Root cause, traced in the source

Full causal chain (Lucebox `server/src/server/prefix_cache.cpp` and
`http_server.cpp`):

```text
cache full (cap_=4) + linear conversation
        ↓
entries_ = [A, B, C, D] with A ⊂ B ⊂ C ⊂ D
        ↓
select_inline_evict_victim(): skips every entry that is a strict prefix of
another ("ancestor", protected). In a linear chain only D is not
        ↓
D is the ONLY eligible leaf — but it is also the slot being restored from
        ↓
prepare_inline_snap() reuses the victim's slot as the destination
        ↓
snap_slot == cache_slot
        ↓
guard in http_server.cpp: "Never destroy the snapshot needed by this
request's restore" → cancel_inline_snap()
        ↓
no new snapshot created. D remains the frontier. Next turn: identical
        ↓
LIVELOCK
```

The non-obvious part: **the snapshot is not created and then sacrificed — it is
never created at all.** The reservation collides with the restore slot and is
cancelled before generation begins.

The ancestor-protection heuristic is correct for a conversation tree with real
branching; in a strictly linear chain — the normal case for a coding agent
loop — it produces the opposite effect: it permanently protects the oldest
ancestors and systematically makes the only useful entry evictable.

**The HTTP guard is not the bug.** It prevents overwriting the KV the request
is still reading from: removing it would turn a performance problem into state
corruption. The defect is upstream, in victim selection.

## 3. PR #665 got there first — two days earlier

The upstream alignment check was done **after** implementing and validating a
fix of our own. It found
[Luce-Org/lucebox#665](https://github.com/Luce-Org/lucebox/pull/665)
("fix(server): slide the prefix-cache restore point past the deepest slot", by
`jkyamog`), **open since 26 August 2026**, with the same causal chain and the
same class of correction.

Point-by-point comparison between their patch and our independent
implementation:

| | PR #665 | ours |
|---|---|---|
| root cause | only leaf = restore source → guard cancels | identical |
| exclusion parameter | `skip_index` | `exclude_idx` |
| physical slot identity, not length | `restore_source_slot` | identical |
| both call sites (chat + agent-turn-cache) | yes | yes |
| `pending_protect_` leak | yes | yes |
| `-1` sentinel | yes | yes |
| HTTP guard left intact | yes | yes |
| fallback | **shallowest** unprotected ancestor | oldest **branch-aware** ancestor |

The two defects we initially presented as "found while implementing" — the
second call site and the `pending_protect_` leak — were **already covered** by
#665.

**Retraction on record.** The branch-awareness of our fallback was justified by
saying it avoided "orphaning a live side branch". That is imprecise: every
cache entry is a self-contained snapshot (its own `ids` and slot), so removing
an ancestor invalidates no descendant. The real cost is only losing a restore
point for a *future* diverging branch. It is a policy choice, not an
improvement to claim.

## 4. What is actually ours

Not "we found and fixed it". The correct formulation:

> Independently reproduced, diagnosed and implemented a fix for a prefix-cache
> livelock; a subsequent upstream comparison showed that PR #665, opened two
> days earlier, had independently identified substantially the same root cause
> and the same fix. The actual contribution is independent AMD/ROCm validation
> and the reproducer methodology.

**No competing PR was opened** — it would have been a duplicate. A validation
comment was published on #665
([issuecomment-5458389311](https://github.com/Luce-Org/lucebox/pull/665#issuecomment-5458389311)).

### 4.1 Cross-vendor validation

Upstream verifies on NVIDIA RTX 3090. To make the comparison honest, patch
#665 was applied to our own base (`136ad9c`, clean apply), rebuilt, and run
with identical parameters against the unpatched binary — same machine, same
session, back to back.

| 16 turns, 4 slots, with tools | pre-fix | **PR #665** | our impl. |
|---|---|---|---|
| `prefix_len` past saturation | **frozen at 3072** for 12 turns | 3072 → 7680 | 3072 → 7680 |
| snapshots committed | 4 | **14** | 14 |
| eviction attempts | 12 | 3 | 3 |
| victim chosen | deepest entry, **12/12** | redundant ancestor | redundant ancestor |
| total prefill | 65.2 s | **29.0 s** | 30.6 s |
| latency at turn 16 | 8.60 s, climbing | **2.45 s, flat** | 2.56 s |

The two implementations are **behaviourally identical** on this workload: same
`prefix_len` sequence turn by turn, same victim, same protected tools pin
preserved. The four `test_slide_*` unit tests from #665 pass on ROCm.

Hardware: AMD Radeon AI PRO R9700 (gfx1201, 32 GB), ROCm 7.2.1, Ubuntu 24.04.4,
kernel 6.17.0-40. The added value is showing that **the fix is not
incidentally CUDA-specific**.

### 4.2 The reproducer methodology — the most original contribution

**Our first end-to-end reproducer passed against the broken binary.** Ten turns
with small prompts and no tools: only 3 snapshots committed across 4 slots,
zero evictions. The cache never saturated, so the regime where the livelock
lives was never reached. A green run under those conditions could not mean
"the defect is absent".

Turn size and tool-schema presence became **explicit parameters** of the script
for exactly this reason. A multi-turn test can report a false green if it does
not genuinely saturate `--prefix-cache-slots`.

Later investigation sharpened the requirement: to genuinely exercise
`select_inline_evict_victim`, a workload must **simultaneously** confirm enough
snapshots, keep entries alive (few aborts), reach `cap_`, and force the call.

## 5. Production realigned to #665

The production server runs the upstream patch, not our implementation — it
minimizes the local delta and simplifies updating once #665 is merged.

- local branch `prod/pr665-baseline`, commit `062ea1a`, with explicit
  attribution to `@jkyamog` in the message;
- **reproducible build**: the rebuilt binary is bit-identical
  (`md5 0faa4c6e…`) to the artifact that produced the published numbers;
- configuration unchanged from before the restart.

Verification over the first 16 real turns: `prefix_len` 0 → 7680 monotonic, 14
snapshots against 4 evictions, `kept oldest ancestor (len=2016)` on every
eviction (the protected system+tools pin survives), prefill flat at 1.3–3.7 s.

Our implementation remains on `fix/linear-prefix-cache-livelock` as a
historical record of an independent implementation.

## 6. A limit that must be declared

**The subsequent production session does NOT validate the fix.** At 57k of
context and 49 snapshots committed, evictions were still 0:
`select_inline_evict_victim` was never executed once. The excellent measured
performance (prefill 1.4–5.3 s at 57k, advancing frontier) is a real result,
but it measures that the cache never needed to sacrifice an entry — not that
the policy is correct.

The only validation of the fix remains the controlled 16-turn reproducer.

**Why the eviction branch is never taken** (INFERRED, not proven): a snapshot
that is prepared but not confirmed goes through `abort_inline_snap`, which
deletes every entry on that slot and therefore decrements `entries_`. Aborts
**emit no log line at all**, so they cannot be counted from outside. Promoting
the hypothesis to VERIFIED requires instrumenting `abort_inline_snap` (and the
return of `prepare_inline_snap`, otherwise the denominator stays unknown).

Methodological note: our initial claim of "zero aborted snapshots" was invalid
— it was inferred from `inline snapshot requested == committed`, but that line
is emitted **only on the branch that goes on to confirm**. It was an indicator
that, by construction, could not reveal an abort. See
[`findings/methodology/measurement-errors.md`](../methodology/measurement-errors.md)
§M5.

## 7. Side discovery: the R9700 idling at ~95 W

The investigation surfaced a known ROCm issue documented on this exact
hardware: [legacy-rocm-build#5706](https://github.com/ROCm/legacy-rocm-build/issues/5706)
(R9700/gfx1201, llama.cpp HIP backend) and
[legacy-rocm-build#6298](https://github.com/ROCm/legacy-rocm-build/issues/6298) (same GPU with PyTorch).

Details and the four measured states in
[`performance/hardware/rocm-idle-power-gfx1201.md`](../../performance/hardware/rocm-idle-power-gfx1201.md).
Cost: **~70 W**, roughly 1.7 kWh/day leaving the server up for nothing.

Two practical consequences: `gpu_busy_percent` is **unusable** for telling
whether the GPU is working (it saturates in both cases) — use
`mem_busy_percent` and power draw; and stopping the backend when it is not
needed is a real saving.

A detail not present in the upstream issue: the pin appears **after real HIP
work**, not merely from keeping the process alive with the model resident.
With one caveat: **at least one sample at 3%** was observed during a short
pause, so "stays at 100% until the process exits" describes what we observed,
not an established rule.

## 8. Method errors made in this investigation

Recorded in full because they are part of the data, and because they belong to
a recurring class described in
[`findings/methodology/measurement-errors.md`](../methodology/measurement-errors.md):
**inferring runtime completeness from an indicator that observes only a
sub-path of the runtime**.

1. **A reproducer that passed against the broken binary** — it never reached
   the regime where the defect exists (M4).
2. **`gpu_busy=100` read as "the server busy-waits"** — the counter measures
   queue residency; the threads were blocked in `kfd_wait_on_events` at 0.0%
   CPU (M6).
3. **`requested == committed` read as "zero aborts"** — that line is emitted
   only on the confirming branch (M5).

A fourth error, **not** of this class: pinned clocks attributed to the user's
`COMPUTE` power profile, when the contrary evidence had already been collected
(3441 MHz while the profile was still `POWER_SAVING`) and simply not compared
(M7).

**Data loss**: the log of the original ds-harness session (101 requests, the
basis of every livelock analysis) was **destroyed** by restarting the server
without copying it first — the script redirects with `>`. Later analyses rely
on surviving secondary sources.
