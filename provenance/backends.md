# Backends

## llama.cpp + DFlash2

Local build from the `xsn/dflash2` branch of `ggml-org/llama.cpp`, the PR that
introduces DFlash2 (block-wise speculative decoding from z-lab,
[PR #27342](https://github.com/ggml-org/llama.cpp/pull/27342)).

Two independent `llama-server` servers, one per GPU, started with
`--spec-type draft-dflash` and a variable `--spec-draft-n-max`.

Key parameter: **`--spec-draft-n-max`**, the maximum number of tokens the
drafter proposes per block. The optimum differs between the two backends — see
`performance/consolidated-results.md` §1.

## Lucebox

[`Luce-Org/lucebox`](https://github.com/Luce-Org/lucebox), Apache-2.0. Server
inference engine (`dflash_server`) that implements DFlash2 with an architecture
of its own, not derived from llama.cpp for the speculative decoding part.

Key parameter: **`--draft-block-size`**, conceptually analogous but not
identical to `--spec-draft-n-max`: the mechanisms and codebases are different,
and the values are not comparable one to one.

Production configuration used for the agent sessions:

```
--draft-block-size 16
--max-ctx 131000
--cache-type-k q8_0 --cache-type-v q8_0
--prefix-cache-slots 4
--prefill-cache-slots 2
```

`--prefix-cache-slots 4` instead of the native default of 32: each slot is a
full KV snapshot kept in **system RAM**, not in VRAM, and it grows with the
context depth (~2.76 GB/slot observed at 72k tokens). With 32 slots a long
session came close to saturating the RAM.

The agent sessions after 2026-08-29 use the upstream patch
[PR #665](https://github.com/Luce-Org/lucebox/pull/665) — see
`findings/prefix-cache/`.

## Ollama / MTP

Ollama 0.33.1, used as a pre-existing production reference. Configured
**ROCm-only** on this machine (`CUDA_VISIBLE_DEVICES=-1`,
`ROCR_VISIBLE_DEVICES=0`, `HSA_OVERRIDE_GFX_VERSION=12.0.1`), so it cannot use
the 3090 Ti.

## Agent harness

`deepseek-harness` (MIT), with 25 tools exposed to the model.
