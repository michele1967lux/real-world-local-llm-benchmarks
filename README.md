# Real-World Local LLM Benchmarks

Inference and coding-agent measurements on real workstation hardware — with
the problems hit along the way, the wrong conclusions we published and then
retracted, and the raw data to check all of it.

**Hardware**
AMD Radeon AI PRO R9700 32 GB (gfx1201, ROCm 7.2.1)
NVIDIA GeForce RTX 3090 Ti 24 GB (CUDA)
Ryzen 9 3950X · Ubuntu 24.04 · kernel 6.17

**Main model** Qwen3.8-27B
**Backends** llama.cpp + DFlash2 · Lucebox · Ollama/MTP

---

## Contents

| | |
|---|---|
| [`performance/consolidated-results.md`](performance/consolidated-results.md) | **every number, one page** |
| [`coding-agents/`](coding-agents/) | two coding benchmarks, with full task specs and independent judge reports |
| [`findings/prefix-cache/`](findings/prefix-cache/) | the bug that cost 91% of wall-clock, and our validation of the upstream fix |
| [`findings/methodology/`](findings/methodology/) | measurements we got wrong, and how |
| [`raw/`](raw/) | 30 raw JSON result files, never edited |
| [`provenance/`](provenance/) | hardware, models, backend versions |

---

## Headline findings

**DFlash2's optimum is not the same on both backends.** CUDA peaks at
`n-max=4` (+64.8%), ROCm at `n-max=3` (+68.1%). The value we started with,
`n-max=7`, is the **worst** of the five tested on both.

**At 131k context the gain halves on CUDA — but context is not the cause.**
It is KV cache quantization, forced by fitting 131k into 24 GB. A control run
at 4096 with the same quantization shows an almost identical drop (+15.1% vs
+15.3%). The 32 GB R9700 does not need to quantize and keeps **+65.5%**.

**The same backend does 153 tok/s on code and 40 on prose.** Lucebox at
`--draft-block-size 16`: drafter acceptance 62% on code, 16% on prose. Against
llama.cpp on the same hardware it is **2.7× faster on code** and **loses on
prose**. The autoregressive baselines of the two engines are nearly identical
(~28 tok/s), so this is the drafter and the content type, not the GPU.

**Microbenchmarks overstate real agent throughput by roughly 3×.** 153 tok/s
on 50-token HumanEval prompts; **48.8 tok/s** across a real agent session with
75k context and 25 exposed tools. Decode drops by a third going from 20–40k to
60–80k of context.

**A prefix-cache bug cost 91% of wall-clock.** In a linear prefix chain the
only entry eligible for eviction is the very slot the request is restoring
from; a correct safety guard then cancels the reservation, and the cache
frontier never advances — 62 of 91 turns frozen. We diagnosed it in the source
and validated the fix on ROCm, but **the fix is not ours**: upstream PR #665
predates our work by two days.

**On coding benchmarks Qwen3.8 has opposite outcomes.** High-fidelity port of
an existing module: **59** against Claude Code's **87** on the same task.
Greenfield build of a durable job queue: **PASS**, surviving 53/53 of its own
tests and 17/17 independent adversarial tests. In both cases the main defect is
in what it documents, not in the code.

**Leaving the server idle costs ~70 W.** A known, open ROCm bug on this
hardware: after serving at least one request the clocks stay pinned and the
GPU never drops to idle until the process exits.

---

## What makes this different from a published benchmark

The **measurement errors are published too**. Among them:

- a regression test that passed against the broken binary, because it never
  reached the regime where the defect exists;
- a GPU utilization counter read as proof of activity, when it measures
  something else entirely;
- a metric used to rule out a phenomenon it could not, by construction,
  observe;
- filesystem `elapsed` mistaken for actual agent working time.

Each is recorded with the initial conclusion, what falsified it, and how to
avoid the same error. See
[`findings/methodology/`](findings/methodology/measurement-errors.md).

For the same reason **some numbers are deliberately not published**: where a
measurement could not be isolated, it is declared as an estimate or as
unavailable rather than cleaned up.

---

## Layout

```
performance/     measurements: llama.cpp, Lucebox, Ollama, long context, hardware
coding-agents/   coding benchmarks: task specs, judge reports, machine-readable manifests
findings/        bug analyses and methodological lessons
provenance/      hardware, models, backend versions
raw/             immutable raw data
```

Files under `raw/` are **never modified**. Any normalization lives elsewhere
and states which raw file it derives from.

## Related repositories

Executable evidence lives outside this repo, to keep it fast to read and to
avoid mixing research, evidence, and third-party software:

| Repository | Contents |
|---|---|
| `qwen38-durable-job-queue-benchmark` | the judged source with its Git history, immutable tag on the evaluated commit |
| `compaction-extraction-benchmark` | both candidates from the first benchmark (derived from `deepseek-harness`, MIT) |
| fork of `Luce-Org/lucebox` | the branches used for the PR #665 validation |

## Language

Canonical documentation is in English. Italian notes may appear in historical
artifacts and in the judged deliverables, which are preserved exactly as they
were produced.

## License

Documentation and data: CC BY 4.0. Tooling code: Apache-2.0. Third-party
derived material keeps its original license and attribution, declared in the
repository that contains it.
