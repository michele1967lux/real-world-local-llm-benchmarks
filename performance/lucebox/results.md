# Lucebox results (reproduction, sibling repository `lucebox-r9700-eval`)

Primary sources (sibling repository `/home/lux-ai/Video/lucebox-r9700-eval/`, read
only): `PROGRAM-STATE.md`, `README.md`, `NOTES-tool-calling-code-comparison.md`,
`bench/roundA-humaneval-block16.json`, `bench/roundB-prompt-compare-block16.json`,
`bench/roundC-block{8,12,16}.json`, `bench/roundD-baseline-ar-humaneval.json`,
`bench/roundD-baseline-ar-prompt-compare.json`.

## What Lucebox is and why it was evaluated

Lucebox (`github.com/Luce-Org/lucebox`, Apache-2.0) is an inference
server engine (binary `dflash_server`) that implements DFlash2 with a
block drafter different from llama.cpp's autoregressive n-max one
("block-diffusion drafter": 5 layers, dynamic grouped convs, DDTree selector
head). Lucebox publishes on its own blog (`lucebox.com/blog/qwen38-r9700`,
self-reported vendor data, never independently verified before
this work) numbers much higher than those observed on llama.cpp+DFlash2
on the same R9700 (AR baseline 32.3 tok/s, block-8 133.9 tok/s, block-16
208.1 tok/s mean, HumanEval-style, decode-only). The declared purpose of the
sibling repository is to **independently reproduce** these numbers
on one's own hardware, with weights already available locally, and compare them
both with the llama.cpp of the twin repo and with the published values.

Explicitly declared methodological note: the quantization of the target
used in this reproduction is **Q4_K_M**, different from Lucebox's "measured profile"
(**IQ4_XS**) — source: `PROGRAM-STATE.md` §2, `README.md`
lines 67-71.

## Round A — HumanEval-style, block-16, 256 tokens, 10 prompts

Source: `bench/roundA-humaneval-block16.json` (`summary` field).

| Metric | Value |
|---|---:|
| Mean decode tok/s | **153.63** |
| Max decode tok/s | 216.5 |
| Min decode tok/s | 94.8 |
| Mean client e2e tok/s | 143.52 |
| accept_rate | 0.38–0.87 (varies per prompt) |

## Round B — prompt.txt (Italian prose, same prompt as the twin repo), block-16, 256 tokens, 5 runs

Source: `bench/roundB-prompt-compare-block16.json`.

| Run | Decode tok/s | accept_rate |
|---|---:|---:|
| 1 | 40.7 | 0.163 |
| 2 | 40.7 | 0.163 |
| 3 | 40.8 | 0.163 |
| 4 | 40.7 | 0.163 |
| 5 | 40.7 | 0.163 |
| **Mean** | **40.72** | **0.163** |

Bit-deterministic (`temperature=0`), accept_rate flat at 0.163 across
all runs — not measurement noise.

## Round C — block-width sweep, HumanEval-style, 128 tokens, 10 prompts

Source: `bench/roundC-block8.json`, `roundC-block12.json`, `roundC-block16.json`.

| Block size | Mean decode tok/s | Max | Min |
|---:|---:|---:|---:|
| 8 | 112.71 | 128.9 | 87.0 |
| 12 | 139.81 | 189.4 | 87.1 |
| 16 | 153.38 | 200.1 | 86.9 |

Decode throughput **grows monotonically with the block width**
on this hardware/workload: block-8 → block-12 → block-16 is the optimal
value tested (no sweep beyond 16 was executed in this repo). Confirmed
only on HumanEval-style code prompts — an equivalent block-width sweep
was not executed on the prose prompt, so it is not known whether
block-width > 16 would help prose or whether a narrower block would be
better: the data is absent, not merely unreported.

## Round D — AR baseline (without speculative decoding)

Source: `bench/roundD-baseline-ar-humaneval.json`,
`bench/roundD-baseline-ar-prompt-compare.json`.

| Workload | Decode tok/s |
|---|---:|
| HumanEval-style (10 prompts, 128 tok) | 28.57 (max 28.8, min 28.5) |
| prompt.txt (3 runs, 256 tok) | 28.3 (identical across all 3 runs, accept_rate=0.0) |

Both ~28.3-28.57 tok/s fall within ~3% of the ROCm AR baseline of
the twin repo's llama.cpp (27.51 tok/s, see [`performance/llama-cpp/results.md`](../llama-cpp/results.md)) —
used as a sanity check that the two engines load the same target weights
with a comparable "plain" decode speed.

**Accuracy**: no accuracy metric (pass@1, correctness of the
generated code) was measured systematically/quantitatively in
this repo. The only qualitative check is a smoke test
(`PROGRAM-STATE.md`): a real request produced "a correct and
complete Python implementation of an LRU cache" — a single manual
verification, not an accuracy benchmark.

## Direct Lucebox vs llama.cpp comparison — same code prompt

Source: `NOTES-tool-calling-code-comparison.md` (sibling repository) +
`bench/dflash2-rocm-nmax3-humaneval-code10.json` (main repo, same
protocol: 10 HumanEval-style prompts copied verbatim from
`scripts/humaneval_prompts.py`, `n_predict=256`, `temperature=0`, 1 discarded
warmup + 10 measured runs).

| Engine | Config | Mean tok/s | Median | Min | Max |
|---|---|---:|---:|---:|---:|
| llama.cpp ROCm + DFlash2 | `--spec-draft-n-max 3` (twin repo's optimum) | 56.56 | 56.89 | 53.22 | 59.18 |
| Lucebox ROCm + DFlash2 | block-16 (Round A) | **153.63** | — | 94.8 | 216.5 |

**Lucebox wins, ~2.7x faster on code** (153.63 / 56.56 ≈ 2.716),
confirmed against an actually measured llama.cpp baseline on the
same prompts (not only against the number self-reported by Lucebox). On the
llama.cpp side the per-prompt accept_rate on code was 88-100% (vs 40-42%
on prose), but the structural ceiling at n-max=3 (vs Lucebox's block-16)
limits the throughput anyway — it is the block-width headroom, not the
acceptance rate, that explains most of the gap.

## Prose: where Lucebox does NOT beat llama.cpp

Source: `README.md` "Honest comparison" (sibling repository), Rounds B/D above.

| Setup | Decode tok/s | vs its own AR baseline |
|---|---:|---:|
| llama.cpp ROCm, no spec decode (twin repo) | 27.51 | — |
| llama.cpp ROCm + DFlash2 n-max=3 (twin repo, prose optimum) | **46.23** | +68.1% |
| Lucebox ROCm, no spec decode (Round D) | 28.3–28.57 | — |
| **Lucebox ROCm + DFlash2 block-16, same prompt.txt (Round B)** | **40.72** | +44% |

On the exact same prompt (Italian prose, `bench/prompt.txt`, verified
identical between the two repos), **Lucebox (40.72 tok/s) is slower than
optimized llama.cpp+DFlash2 (46.23 tok/s)** — a gap of about -12% against
Lucebox. The accept_rate on this prompt is flat at 0.163
(16.3%), about a third of that observed on the HumanEval prompts
(38-97%). Explanation given in the sibling repository: DFlash2's block
drafter exploits the local structural predictability typical of code
(formatting, naming patterns, syntax), which free natural-language
prose does not offer to the same extent.

**Neither of the two Lucebox numbers (208 tok/s published or 40.72 measured
here) should be read as "the speed of the R9700"** without specifying the type of
workload: it is a workload effect, confirmed by Round D (the AR baseline
is almost identical on code and prose, 28.57 vs 28.3 — the gap opens only
when speculative decoding is active).

## Tool-calling — verified working on both engines

Source: `NOTES-tool-calling-code-comparison.md`. Verification both from Lucebox
source code (`lucebox/server/src/server/http_server.h`,
`http_server.cpp`, `tool_hint.cpp`, `tool_parser.cpp`, `sse_emitter.cpp`)
and empirical: a real `/v1/chat/completions` request with a
`get_weather` tool correctly returned `tool_calls`,
`finish_reason:"tool_calls"`, with `spec_decode_ran:true` and
`accept_rate:0.421875`, `decode_tokens_per_sec:76.1` — speculative
decoding stays active even during a tool-call turn. The only gap
documented in Lucebox's `server/docs/API.md`: `parallel_tool_calls`
is accepted but the calls are generated serially (not blocking for
typical single-tool-per-turn use). The twin repo's `llama-server`, tested in
an identical way, passed the same test.

## Conclusions declared in the sibling repository

1. Lucebox compiles and runs natively on the R9700 (gfx1201, ROCm 7.2.1) with
   weights already available, after a metadata-only repack of the drafter (no
   download, no requantization).
2. The speedup declared by Lucebox is **real and reproduces on code
   generation workloads**: peak 216.5 tok/s (95% of the published peak
   227.8), mean 153.5 tok/s over 10 prompts (74% of the published mean
   208.1) — despite a heavier target quant (Q4_K_M vs Lucebox's IQ4_XS)
   and a non-identical prompt set (not published by Lucebox).
3. **It does not reproduce on the discursive prose workload**: block-16 DFlash2
   achieves only 40.7 tok/s, barely +44% above its own AR baseline and
   **below** the already optimized result of llama.cpp+DFlash2 n-max=3
   on the same prompt (46.23 tok/s).
4. The reproduction is **workload-dependent, not a clear-cut yes/no** — it is
   explicitly defined as "the finding" of the sibling repository.
5. The Q4_K_M/IQ4_XS gap + the repacked drafter plausibly explains part of the
   ~25% discrepancy between the measured mean and the published one on HumanEval,
   but it cannot explain the 5x gap between HumanEval and prompt.txt — that is a
   workload effect.
6. Lucebox's ~2.7x advantage on code holds up even against an actually
   measured llama.cpp baseline on the same prompts, not only against the
   numbers self-reported by Lucebox.

## Summary timeline (`PROGRAM-STATE.md`)

1. Source-fidelity check: confirmed that `github.com/Luce-Org/lucebox` is
   real (README/API.md/RECOMMENDED_SETUPS.md/CMakeLists.txt read);
   the plan pasted by Lux verified as accurate, the only correction:
   `ninja-build` was missing from the assumed apt dependencies.
2. Dependency check: ROCm/hip libraries already present; `ninja` obtained
   without sudo via venv pip.
3. Weights: explicit decision by Lux to reuse local weights already downloaded
   instead of the Lucebox reference weights, to limit disk space
   (~45GB free at the start of the session).
4. Build: CMake configured on the first attempt, 376/376 ninja targets
   compiled, only benign warnings (CURL not found, disables only the
   PFlash proxy, not used).
5. Smoke test/weight compatibility: first attempt with an unmodified GGUF
   drafter **failed** (`unexpected draft arch: dflash`) — the local z-lab
   drafter uses different naming (same architecture). Wrote
   `scripts/repack_dflash2_draft_for_lucebox.py` (pure repack of
   metadata/tensor names, no requant); the first version of the script
   had a prefixing bug, fixed by re-reading the call sites of the
   C++ loader. Second attempt successful, with logs confirming the fidelity
   of the repack (conv kernel=2/group=16, selector rank=256/top_k=16,
   vocab=248320, SWA window=2048 on 5/5 layers identical to the original
   metadata).
6. Benchmark: rounds A, B, C as requested plus round D added on my own
   initiative (AR baseline measured directly instead of trusting only the
   32.3 tok/s self-reported by Lucebox).
7. Follow-up 2026-08-28: tool-calling + equal-footing comparison on code
   (see above).
8. GPU/port hygiene: R9700 verified free before every launch (2-3%
   util, no KFD PID), port 8216 always verified free, 7 total launches
   of `dflash_server` all terminated cleanly, disk stable at 42GB
   free at the end of the session (started from 44-45GB).

## Data not available / not measured in this repo

- Systematic accuracy metrics (pass@1 or similar) — only a single
  manual verification (LRU cache).
- Block-width sweep on the prose prompt (only on HumanEval-style).
- Sweep beyond block-16.
