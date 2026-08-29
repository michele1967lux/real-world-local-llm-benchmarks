# llama.cpp + DFlash2 results (CHARTER-0001 / CHARTER-0002 / CHARTER-0003)

Raw data: [`raw/llama-cpp/`](../../raw/llama-cpp/).

These measurements were produced under three charters (CHARTER-0001 dual
backend, CHARTER-0002 n-max sweep, CHARTER-0003 long context) in the private
working repository. The charters themselves are not published; every number
below is traceable to a raw JSON file in this repository.

Protocol: see [`provenance/`](../../provenance/). Fixed prompt (Italian
prose on speculative decoding), `n_predict=256`, `temperature=0`, 1 discarded
warmup run + 5 measured runs per scenario (protocol refined on
2026-08-28 — the initial numbers at 3 runs without warmup are documented as
SUPERSEDED in `PROGRAM_STATE.md` and are not used here).

## CHARTER-0001 — baseline vs DFlash2, `--spec-draft-n-max=7` (upstream default)

Source: `bench/baseline-cuda.json`, `bench/dflash2-cuda.json`,
`bench/baseline-rocm.json`, `bench/dflash2-rocm.json`.

| Backend | Baseline tok/s (mean / median / stddev) | DFlash2 n-max=7 tok/s (mean / median / stddev) | Gain |
|---|---|---|---:|
| CUDA (RTX 3090 Ti) | 25.16 / 25.08 / 0.42 | 30.41 / 30.43 / 0.43 | +20.9% |
| ROCm (AMD R9700 Pro) | 27.51 / 27.51 / 0.14 | 34.34 / 34.35 / 0.15 | +24.8% |

Historical note (`CHANGELOG.md`): the first measurement (3 runs, no warmup) had
given +13.8% CUDA (23.86→27.16 tok/s) and +17.1% ROCm (27.63→32.36 tok/s); a
warmup outlier in the ROCm+DFlash2 run led Lux to ask for the
refined protocol (warmup + median/stddev). The numbers in the
table above are those of the refined protocol and are the ones to cite.

## CHARTER-0002 — `--spec-draft-n-max` sweep: n-max=7 was sub-optimal

Lux pointed to an external benchmark (`thc1006/qwen3.8-speculative-decoding-rtx3090`)
which reports n-max=7 as the **worst** point for DFlash2 on RTX 3090.
Confirmed on this hardware, on both backends.

Source: `bench/dflash2-cuda-nmax{2,3,4,5}.json`, `bench/dflash2-rocm-nmax{2,3,4,5}.json`,
plus the n-max=7 points from CHARTER-0001.

| n-max | CUDA tok/s (gain vs baseline 25.16) | CUDA acceptance | ROCm tok/s (gain vs baseline 27.51) | ROCm acceptance |
|---|---|---:|---|---:|
| 2 | 36.55 (+45.2%) | 72.9% | 45.22 (+64.4%) | 78.8% |
| 3 | 36.47 (+44.9%) | 67.2% | **46.23 (+68.1%)** | 69.9% |
| **4** | **41.47 (+64.8%)** | 62.5% | 43.06 (+56.5%) | 57.8% |
| 5 | 34.05 (+35.3%) | 52.1% | 40.42 (+46.9%) | 51.3% |
| 7 | 30.41 (+20.9%) | 42.1% | 34.34 (+24.8%) | 39.8% |

Acceptance rate computed as `draft_n_accepted / draft_n` of the first run of
each JSON file (a value stable across runs for the same scenario).

**The optimum is not the same on the two backends**: CUDA peaks at **n-max=4**
(+64.8%), ROCm peaks at **n-max=3** (+68.1%, with n-max=2 very close at
+64.4%). The acceptance rate is monotonically decreasing in n-max on both
backends (shorter blocks are easier to accept in full), but the
tok/s is not: an n-max that is too low does not exploit the drafter enough per
block, an n-max that is too high wastes compute on long blocks often rejected
halfway through.

Additional observations (source: `README.md`, `PROGRAM_STATE.md`):

- The preliminary claim "ROCm support uncertain" (contradictory external
  sources) is **positively refuted**: DFlash2 works without
  crashes on ROCm/R9700 with gains higher than CUDA in nearly all the
  n-max values tested.
- The gap with the external benchmark cited by Lux (+52-60% on RTX 3090) was
  largely the sub-optimal n-max parameter: with the right value per
  backend, the gain measured here (+64.8% CUDA, +68.1% ROCm) is in the
  same order of magnitude as, or higher than, the external range.
- ROCm turned out to be faster than CUDA in absolute value (tok/s) on nearly
  all the scenarios tested on this host — an honest additional data point, not
  a prediction of the charter.

## CHARTER-0003 — benchmark at context 131072

Lux asked to repeat the measurement at the context size (131072) used in
production by Ollama for the same blob, suspecting that the DFlash2
gain seen at `-c 4096` would not hold up in a real comparison. Same
protocol, with additional controls at `-c 4096` measured in the SAME
session (the CHARTER-0001/0002 numbers come from a different session —
see the note on drift below).

Source: `bench/baseline-cuda-ctx4096-control.json`,
`bench/dflash2-cuda-ctx4096-control.json`,
`bench/baseline-rocm-ctx4096-control.json`,
`bench/dflash2-rocm-ctx4096-control.json`,
`bench/baseline-cuda-ctx131k.json`, `bench/dflash2-cuda-ctx131k.json`,
`bench/baseline-rocm-ctx131k.json`, `bench/dflash2-rocm-ctx131k.json`,
`bench/baseline-cuda-ctx4096-q4-control.json`,
`bench/dflash2-cuda-ctx4096-q4-control.json`.

| Scenario | tok/s (mean) | Gain vs baseline on the same row |
|---|---:|---:|
| CUDA baseline @ 4096, fp16 (same-session control) | 30.22 | — |
| CUDA DFlash2 n-max=4 @ 4096, fp16 (control) | 38.49 | +27.4% |
| CUDA baseline @ 4096, KV q4_0 (cause-isolation control) | 34.86 | — |
| CUDA DFlash2 n-max=4 @ 4096, KV q4_0 (cause-isolation control) | 40.11 | +15.1% |
| CUDA baseline @ **131072** (KV quantized q4_0, mandatory for VRAM) | 41.78 | — |
| CUDA DFlash2 n-max=4 @ **131072** | 48.19 | **+15.3%** |
| ROCm baseline @ 4096, fp16 (same-session control) | 27.36 | — |
| ROCm DFlash2 n-max=3 @ 4096, fp16 (control) | 45.61 | +66.7% |
| ROCm baseline @ **131072** (fp16, no quantization needed) | 27.50 | — |
| ROCm DFlash2 n-max=3 @ **131072** | 45.51 | **+65.5%** |

**VRAM deviation on CUDA** (explicitly declared, not hidden): at
`-c 131072` the fp16 KV cache of the target model alone exceeds the 24GB of the
RTX 3090 Ti (confirmed by a real startup probe, immediate OOM on the compute
buffers). This wave uses `--cache-type-k/-v q4_0` for the target model and
`--cache-type-k/-v-draft q8_0` for the drafter, ONLY on CUDA — ROCm (32GB)
does not need it. Isolating the cause with the `q4_0` control at `-c
4096` too (+15.1%, almost identical to the +15.3% observed at 131072): **the drop
in gain on CUDA is not caused by the context size in itself, but by the
quantization of the KV cache made mandatory by VRAM** — which at 131072 on this card
is unavoidable, so it remains the real operational number for a
long-context deployment on CUDA.

### Explicit comparison with Ollama/MTP

Data requested by Lux "for comparison" — provided by the coordinator, not
re-measured in this wave (`journalctl -u ollama` + `gpu-monitor.csv`):
Ollama (Vulkan, native MTP — a different mechanism from DFlash2), same blob,
`num_ctx=131072`, real coding-agent load: **mean 47.5 tok/s** (min
15.0, max 85.6, 99 samples).

Compared with the DFlash2 figures of this wave at `-c 131072`: **48.19 tok/s CUDA,
45.51 tok/s ROCm** — same order of magnitude, no clear jump. It is not
a clean comparison (variable real load vs short fixed prompt, MTP vs
DFlash2, Vulkan vs native CUDA/ROCm, context actually filled vs
allocated-but-almost-empty), but Lux's suspicion ("that it is not a
real improvement" relative to Ollama) is **quantitatively supported**
by the direct comparison at the same context scale — even though the gain
vs the pure baseline (without speculative decoding) remains positive in every
scenario measured.

**Out of scope in CHARTER-0003** (explicitly declared): the fixed
prompt used allocates 131072 tokens but USES only ~300-350 of them (short prompt +
`n_predict=256`) — it measures the overhead of a large KV buffer with an almost
empty context, not the degradation at a REALLY full context (e.g. 32-64k
real tokens). Not executed due to the budget of this wave.

### Session-to-session drift on CUDA

`PROGRAM_STATE.md` documents a session-to-session measurement drift on absolute
CUDA tok/s of up to +45% between nominally identical measurements at different
times, absent on ROCm — noted as a reading caveat for every CUDA
number in this repo (the numbers on this page all come from the same
session declared in the relevant JSON file, not mixed across different
sessions).

## HumanEval-style context (ref. Lucebox comparison, details in [`performance/lucebox/results.md`](../lucebox/results.md))

Source: `bench/dflash2-rocm-nmax3-humaneval-code10.json`.

| Scenario | tok/s (mean / median) | n_runs | Notes |
|---|---:|---:|---|
| ROCm DFlash2 n-max=3, 10 HumanEval-style prompts, `-rea off` | 56.56 / 56.89 | 10 | vs 46.23 tok/s at the same n-max on the prose prompt — code-type content has a higher drafter acceptance rate (88-100% per prompt vs ~70% on prose) |

Methodological note cited by the JSON file itself (`methodology_note`): the
`-rea off` flag (`--reasoning off`) was added after diagnosing
that, with the "thinking" of the target GGUF (Qwen3.8-27B, thinking-capable
chat template) left active, the entire budget of 256 tokens was
consumed by `reasoning_content` with zero characters of code returned on
some prompts (`content_len=0`, `reasoning_content` non-empty); with
raw `/completion` (no chat template) 3/10 prompts instead returned
a single empty token. Both are documented failure modes
of NOT applying `-rea off`.

## General observation — the optimal n-max depends on the content

Comparing the n-max sweep on prose (CHARTER-0002, table above) with the
HumanEval-style point above: at the same n-max=3, code yields
56.56 tok/s against 46.23 tok/s on prose — the drafter's acceptance rate is
the common mechanism that explains both the sensitivity to n-max and the
sensitivity to the type of content (code is more locally predictable →
blocks accepted more often and for longer).
