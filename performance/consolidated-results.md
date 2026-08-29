# Consolidated results

Every measured number in one place. Each table states the raw file it comes
from and the protocol that produced it.

**Results are not comparable across sections.** A microbenchmark `tok/s` and a
code-quality verdict are different dimensions; there is no single ranking that
contains both.

Hardware, models and backends: see [`provenance/`](../provenance/).

---

## 1. Backend microbenchmark — llama.cpp + DFlash2

Fixed prompt (Italian prose), `n_predict=256`, `temperature=0`, 1 discarded
warmup run + 5 measured runs. Context 4096, KV fp16.

Source: `raw/llama-cpp/baseline-{cuda,rocm}.json`,
`raw/llama-cpp/dflash2-{cuda,rocm}-nmax{2,3,4,5}.json`,
`raw/llama-cpp/dflash2-{cuda,rocm}.json` (n-max=7).

Baseline without speculative decoding: **CUDA 25.16 tok/s**, **ROCm 27.51 tok/s**.

| `--spec-draft-n-max` | CUDA tok/s | gain | acceptance | ROCm tok/s | gain | acceptance |
|---|---:|---:|---:|---:|---:|---:|
| 2 | 36.55 | +45.2% | 72.9% | 45.22 | +64.4% | 78.8% |
| 3 | 36.47 | +44.9% | 67.2% | **46.23** | **+68.1%** | 69.9% |
| 4 | **41.47** | **+64.8%** | 62.5% | 43.06 | +56.5% | 57.8% |
| 5 | 34.05 | +35.3% | 52.1% | 40.42 | +46.9% | 51.3% |
| 7 | 30.41 | +20.9% | 42.1% | 34.34 | +24.8% | 39.8% |

**The optimum differs between backends**: CUDA peaks at n-max=4, ROCm at
n-max=3. Acceptance decreases monotonically with n-max on both — shorter
blocks are easier to accept whole — but throughput does not: too low and the
drafter is underused, too high and compute is wasted on blocks rejected
halfway.

n-max=7, the value we initially used, is the **worst** of the five on both
backends.

---

## 2. Long context — 131k tokens

Source: `raw/llama-cpp/*-ctx131k.json` and `*-ctx4096-*control*.json`.

| Scenario | tok/s | gain |
|---|---:|---:|
| CUDA baseline @4096 fp16 (control) | 30.22 | — |
| CUDA DFlash2 n-max=4 @4096 fp16 | 38.49 | +27.4% |
| CUDA baseline @4096 **KV q4_0** (isolation control) | 34.86 | — |
| CUDA DFlash2 n-max=4 @4096 **KV q4_0** | 40.11 | **+15.1%** |
| CUDA baseline @**131072** (KV q4_0, mandatory) | 41.78 | — |
| CUDA DFlash2 n-max=4 @**131072** | 48.19 | **+15.3%** |
| ROCm baseline @4096 fp16 (control) | 27.36 | — |
| ROCm DFlash2 n-max=3 @4096 fp16 | 45.61 | +66.7% |
| ROCm baseline @**131072** (fp16, no quantization) | 27.50 | — |
| ROCm DFlash2 n-max=3 @**131072** | 45.51 | **+65.5%** |

**The DFlash2 gain halves on CUDA at long context — but context is not the
cause.** At 131072 the fp16 KV cache exceeds the 3090 Ti's 24 GB (verified: OOM
at startup), so CUDA requires a quantized KV. Isolating the variable with a
control at 4096 *using the same quantization* gives an almost identical drop:
**+15.1% vs +15.3%**. KV quantization eats the benefit, not context length.

The 32 GB R9700 never needs to quantize and holds **+65.5%**.

---

## 3. Lucebox — decode on code vs prose

Source: `raw/lucebox/round{A,B,C,D}*.json`. 256 generated tokens,
`temperature=0`, metric `server_decode_tok_per_s`.

| Configuration | content | decode tok/s | acceptance |
|---|---|---:|---:|
| AR baseline (no speculation) | code | 28.57 | — |
| `--draft-block-size 8` | code | 112.71 | 82.6% |
| `--draft-block-size 12` | code | 139.81 | 71.3% |
| **`--draft-block-size 16`** | code | **153.38–153.63** | 61.4–61.8% |
| AR baseline | prose | 28.30 | — |
| `--draft-block-size 16` | **prose** | **40.72** | **16.3%** |

**The code/prose gap is the sharpest result in this repository.** Same
backend, same model, same configuration: 153.63 tok/s on code, 40.72 on prose.
Drafter acceptance collapses from ~62% to 16%.

Head-to-head with llama.cpp on the same hardware:

| | Lucebox block16 | llama.cpp ROCm n-max=3 | ratio |
|---|---:|---:|---:|
| code (HumanEval-style) | 153.63 | 56.56 | **2.7×** for Lucebox |
| prose | 40.72 | 46.23 | **0.88×** — Lucebox loses |

llama.cpp code source: `raw/llama-cpp/dflash2-rocm-nmax3-humaneval-code10.json`.

Neither Lucebox number represents "the speed of the R9700": the two engines'
autoregressive baselines are nearly identical (~28 tok/s on both content
types). The difference is entirely the drafter and the kind of text.

---

## 4. Real agent session — what microbenchmarks don't show

Full ds-harness session (the "Durable Job Queue" benchmark), Lucebox backend
with upstream patch #665, `--prefix-cache-slots 4`, `--max-ctx 131000`.

| | |
|---|---:|
| turns served | 87 (0 errors) |
| server time | 24.8 min |
| tokens generated | 51,575 |
| weighted mean decode | **48.8 tok/s** |
| DFlash2 acceptance | 54.2% |
| context | 11.7k → 75.6k tokens |
| prefill | 26% of wall-clock |
| decode | 71% of wall-clock |

Decode by context band:

| context | decode tok/s |
|---|---:|
| 0–20k | 46.0 |
| 20–40k | **57.9** |
| 40–60k | 51.9 |
| 60–80k | **38.3** |

**48.8 tok/s against 153.63 in the microbenchmark, same backend.** The
HumanEval microbenchmark uses ~50-token prompts and generates 256 tokens; a
real agent session carries 75k of context, 25 exposed tools, and alternates
long generations with replies of a few dozen tokens. The ~3× gap is the
distance between synthetic benchmark and real load, not a measurement error.

Decode falls by about a third going from 20–40k to 60–80k of context.

### The same session before the prefix-cache fix

| | pre-fix (101 requests) | post-fix (87 turns) |
|---|---:|---:|
| prefill / wall-clock | **76%** | **26%** |
| prefill/decode ratio | 3.31× | **0.36×** |
| mean time per turn | 97.9 s | 16.5 s |
| turns with frozen frontier | 62 of 91 (68%) | 0 |

**Required caveat**: pre-fix prompts were 72k–77k against 11k–75k post-fix.
The 5.9× ratio on time-per-turn **conflates smaller context with the fix** and
is not attributable to the patch alone. The scale-robust signal is the
prefill/decode inversion and the advancing frontier, not the multiplier.

Details in [`findings/prefix-cache/linear-livelock.md`](../findings/prefix-cache/linear-livelock.md).

---

## 5. Code quality — a separate axis

**These results are not comparable with the sections above.** They evaluate
deliverables, not throughput.

| Benchmark | Type | Outcome |
|---|---|---|
| Compaction extraction | high-fidelity port of an existing module | Qwen3.8 **59** / Claude Code **87** |
| Durable job queue | greenfield, from scratch | Qwen3.8 **PASS with 2 defects** |

The first compares two candidates on the same task; the second has a single
candidate, so its PASS is absolute, not relative. Lining them up as one scale
mixes two different axes.

Task specs, judge reports and details in [`coding-agents/`](../coding-agents/).

---

## 6. Idle power cost

| R9700 state | power | junction |
|---|---:|---:|
| server stopped | 22–36 W | 67 °C |
| server up, model loaded, nothing served yet | 18–31 W | 56 °C |
| **server idle after serving** | **93–105 W** | 80–82 °C |
| server under load | 291 W | 110 °C |

About **70 W** between a stopped server and one idling after use — roughly
1.7 kWh/day if left running for nothing. This is a known ROCm issue on this
hardware, not a misconfiguration — closed upstream as completed, but still
reproducing on ROCm 7.2.1.

Details in
[`performance/hardware/rocm-idle-power-gfx1201.md`](hardware/rocm-idle-power-gfx1201.md).

---

## How these numbers were produced

The protocol, the measurement errors made and corrected, and the reasons some
numbers are **not** published — for example an exact "active time" for the
coder session — are in
[`findings/methodology/`](../findings/methodology/measurement-errors.md).
