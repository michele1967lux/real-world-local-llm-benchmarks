# Measurement errors — conclusions we published and then retracted

Each entry follows the same shape: what we concluded, why it was wrong, what
falsified it, the correct conclusion, and how to avoid the same error.

They are collected here because published benchmarks normally omit them, and
because several belong to **one recurring class**, described at the end.

---

## M1 — HIP warmup distorted the DFlash2 gain

**Initial conclusion.** DFlash2 gives +13.8% on CUDA and +17.1% on ROCm.

**Why it was wrong.** Three runs per scenario, no discarded warmup. The first
ROCm run included HIP initialization, which inflates the baseline run's time
and compresses the apparent gain.

**What falsified it.** An obvious outlier in the ROCm+DFlash2 run, visible in
the spread of the timings.

**Correct conclusion.** With 1 discarded warmup run + 5 measured runs, and
reporting median and standard deviation alongside the mean: **+20.9% CUDA**,
**+24.8% ROCm** (at n-max=7).

**How to avoid it.** On ROCm the first run of a process is never
representative. Always publish the spread: a standard deviation nobody sees is
a standard deviation nobody looked at.

---

## M2 — KV quantization mistaken for a context-length effect

**Initial conclusion.** At 131k context the DFlash2 gain on CUDA collapses
from +64.8% to +15.3%: long context reduces the benefit of speculative
decoding.

**Why it was wrong.** At 131072 the fp16 KV cache does not fit in the 3090
Ti's 24 GB, so that scenario — and only that one — uses `q4_0` quantized KV.
The two measurements differed by **two** variables, not one.

**What falsified it.** A control added specifically for this: baseline and
DFlash2 at 4096 **with the same q4_0 quantization**. Gain +15.1%, practically
identical to the +15.3% at long context.

**Correct conclusion.** KV quantization eats the benefit, not context length.
The 32 GB R9700 does not need to quantize and keeps +65.5% at 131k.

**How to avoid it.** When a hardware constraint forces a configuration change
alongside the variable under study, the measurement has two variables. Either
add a control that isolates the unwanted one, or the conclusion cannot be
drawn.

---

## M3 — HumanEval overstated agent throughput by ~3×

**Initial conclusion.** Lucebox does 153 tok/s on code, so a real coding
session will run near that.

**Why it was wrong.** HumanEval prompts are ~50 tokens and generate 256 tokens
in one shot. An agent session carries 75k of context, 25 exposed tools, and
alternates long generations with replies of a few dozen tokens.

**What falsified it.** A real session measured end to end: **48.8 tok/s**
average over 87 turns.

**Correct conclusion.** The microbenchmark measures the decoder's peak under
favourable conditions; real load sees about a third of it. Both numbers are
correct; they measure different things.

**How to avoid it.** Do not extrapolate from a short-prompt benchmark to agent
load. If the second is what matters, measure the second.

---

## M4 — A regression test that passed against the broken binary

**Initial conclusion.** The end-to-end reproducer passes: the prefix-cache
livelock does not occur.

**Why it was wrong.** Ten turns with small prompts and no tool schema: the
cache reached 3 snapshots out of 4 slots and **never saturated**. The livelock
only exists at saturation. The test could not fail.

**What falsified it.** Inspecting the logs: zero evictions across the whole
run. A test that produces no eviction at all is not testing the eviction
policy.

**Correct conclusion.** With larger turns and a tool schema — parameters made
explicit precisely because of this — the livelock reproduces: frontier frozen
for 12 consecutive turns, latency climbing from 1.6 s to 8.6 s.

Later investigation sharpened the requirement: to genuinely exercise victim
selection, a workload must **simultaneously** confirm enough snapshots, keep
entries alive, reach capacity, and force the call.

**How to avoid it.** Before accepting a green run, ask whether the test
entered the regime where the defect exists — and verify it with a counter, not
by intuition.

---

## M5 — A metric that could not, by construction, observe what it was used to rule out

**Initial conclusion.** Zero aborted snapshots in the session, because
`inline snapshot requested` = 49 = `inline-snap committed`.

**Why it was wrong.** That log line is emitted **only on the branch that goes
on to confirm**. The abort function prints nothing. The metric could not, under
any circumstance, reveal what was being ruled out.

**What falsified it.** Reading the source: `abort_inline_snap` has no
`fprintf` at all, and is reached through an `else` branch the logging does not
cover.

**Correct conclusion.** The number of aborts is **unknown**. The hypothesis
that they are what keeps the cache below capacity remains plausible but
unproven, and proving it requires instrumenting the code.

**How to avoid it.** This is the purest form of the class described below:
before using an observation as proof of absence, verify the observer is
capable of producing a signal when the phenomenon is present.

---

## M6 — A GPU utilization counter read as proof of activity

**Initial conclusion.** `gpu_busy_percent` sits at 100% with the server idle,
so the server is busy-waiting on the GPU.

**Why it was wrong.** That counter reflects queue residency and command
processor activity — not shader work, and certainly not CPU spinning.

**What falsified it.** The process's thread states: all blocked in
`kfd_wait_on_events`, at **0.0% CPU**. A blocking kernel wait, not a spin.

**Correct conclusion.** The GPU is idle. The indicators that actually
discriminate are `mem_busy_percent` (0–4% idle vs ~53% under load) and power
draw (~95 W vs ~291 W). `gpu_busy_percent` saturates in both cases and is
useless for this purpose.

**How to avoid it.** Before interpreting a counter, check what it measures. If
a direct indicator of the phenomenon exists — here, thread state — look at
that one.

---

## M7 — A cause assigned without comparing data already collected

**Initial conclusion.** The GPU clocks are pinned at maximum because the user
set the `COMPUTE` power profile.

**Why it was wrong.** The clocks were **already** at 3441 MHz drawing 96 W
while the profile was still `POWER_SAVING`. The data had been collected and
simply not compared.

**What falsified it.** Comparing the two readings, then a literature check: it
is a known, open ROCm bug on this hardware.

**Correct conclusion.** The profile is irrelevant. A HIP runtime bug prevents
the GPU from dropping to idle after it has served work.

**Note.** This one does **not** belong to the class below: the contrary
evidence was available; what was missing was the act of looking at it. A
different error with a different remedy — re-read the data you already hold
before naming a cause.

---

## M8 — Filesystem `elapsed` mistaken for working time

**Initial conclusion.** The Sonnet 5 agent took ~57 minutes, measured from the
first to the last mtime in its directory.

**Why it was wrong.** The first file (`TASK.md`) had been written by the
operator 27 minutes before the agent started, to prepare the directory. The
method included time that was not the agent's work.

**What falsified it.** Timestamps from the agent's own transcript:
23:06:02 → 23:36:37, **30.6 minutes**, independently confirmed by the
framework's `duration_ms`.

**Correct conclusion.** 30.6 minutes. And the more important point: the same
method applied to the other candidate added ~15 minutes to a 10.6-hour total —
negligible, 2% — but 33 minutes to 30 minutes of real work. **A systematic
error that weighs completely differently at two scales is not a consistent
methodology**, even when the procedure is identical.

**How to avoid it.** Verify that the first and last events of the measured
window belong to the subject being measured. And assess the size of the bias
relative to each measurement, not in absolute terms.

---

## M9 — A plateau mistaken for a stall

**Initial conclusion.** `prefix_len` has not moved for four turns: the
livelock is back.

**Why it was wrong.** The cache frontier advances in jumps, at message
boundaries. A turn that generates 5,825 tokens as a single message offers no
cut point until it closes.

**What falsified it.** Prefill, which stayed at 0.9–3.3 s. In a real livelock
the gap between frontier and prompt grows without bound and prefill grows with
it, up to 120–140 s. On the next turn the frontier jumped forward by 6.1k
tokens at once.

**Correct conclusion.** The discriminator is not a static `prefix_len`, it is
a static `prefix_len` **while the gap to the prompt grows and prefill grows
with it**.

**How to avoid it.** A single indicator that moves in jumps cannot distinguish
a plateau from a stall. You need the quantity the stall makes grow
monotonically.

---

## M10 — Green tests written by the same author as the code

**Initial conclusion.** The candidate reports 22/22 tests passing, so the
extracted module is equivalent to the original.

**Why it was wrong.** The tests were written by the same author as the
implementation, against that implementation. They verify internal consistency,
not equivalence with the source.

**What falsified it.** Reconstructing and **executing the original** against
the same external harness as the candidates. Three confirmed behavioural
divergences that code inspection had not revealed.

**Correct conclusion.** A green test written by the author proves the code
does what the author believed. Equivalence requires an executed differential
against the real source.

**How to avoid it.** When judging a port, run the source. When judging a
greenfield build, write independent tests against the specification — not
against the delivered code.

---

## The recurring class

M4, M5 and M6 are the same thing:

> **Inferring runtime completeness from an indicator that observes only a
> sub-path of the runtime** — using as proof an observer that, by
> construction, cannot exhibit the negative case being ruled out.

In M4 the test never entered the regime where the defect lives. In M5 the
metric existed only on the success branch. In M6 the counter measured a
different quantity than the one inferred from it.

**The guard.** Before using an observation as proof of absence, answer
explicitly:

> *would this observer have produced a different signal if the phenomenon were
> present?*

If the answer is no, or uncertain, the observation can at most be
`CHARACTERIZED`, never `VERIFIED`. This applies to regression tests exactly as
much as to telemetry: it is the same question that keeps a reproducer from
being vacuous.

M7 and M8 do not belong to this class. M7 is failure to use evidence already
in hand; M8 is a systematic bias not assessed relative to the scale of the two
measurements. Different remedies, and worth keeping distinct rather than
padding the count.

---

## One data loss

The log of the original agent session — 101 requests, the basis of every
livelock analysis — was **destroyed** by restarting the server without copying
it first: the startup script redirects with `>`. Later analyses rely on
surviving secondary sources, and say so where it matters.
