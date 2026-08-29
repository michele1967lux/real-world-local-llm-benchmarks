# Ollama/MTP as a production reference point

Ollama was the pre-existing production setup on this machine, so it is the
only baseline that reflects what the hardware was actually delivering before
any of this work. It is included for that reason — but the comparison has
limits that have to be stated before the numbers.

## The numbers

| | Ollama/MTP (Vulkan, earlier real session) | Lucebox DFlash2 (native ROCm, real session) |
|---|---:|---:|
| mean | 47.5 tok/s | 45.2 – 57.4 tok/s (depending on configuration) |
| standard deviation | 19.9 | 9.5 – 15.3 |

The same Ollama/MTP figure (47.5 tok/s) also appears in our CHARTER-0003 notes
as the reference for a long-context (131k) comparison — internally consistent
across two documents.

## Three limits, declared

**1. This is not a controlled A/B.** The Ollama number comes from an earlier
real session, not from a run executed alongside Lucebox under identical
conditions. Different sessions, different content, different context depths.

**2. The historical CSV cannot arbitrate it.** In `gpu-monitor.csv`, the
`gen_tok_s` / `prompt_tok_s` columns are extracted **exclusively** from
`journalctl -u ollama` — they never contain Lucebox throughput. The
thermal/power/VRAM columns come from `rocm-smi` and are generic for whatever
process is on the GPU at that moment, with no backend label in the CSV.

So the CSV contains **no direct Lucebox-vs-Ollama comparison**. The table above
comes entirely from direct observation recorded in our notes, not from an
automated extraction.

For completeness, general CSV statistics over active rows (n=99):
`gen_tok_s` min 14.98, max 85.61, mean 47.08 — compatible in order of
magnitude with the 47.5 tok/s cited for Ollama/MTP, but not necessarily the
same sample or session.

**3. Different stacks, not just different engines.** Ollama here runs on
Vulkan; Lucebox runs native ROCm. Attributing the difference to speculative
decoding alone would be wrong.

## What can be said

The two are in the **same order of magnitude** on real agent load. DFlash2 via
Lucebox shows a **lower standard deviation** (9.5–15.3 against 19.9), i.e.
more consistent throughput, which for an interactive coding loop matters
alongside the mean.

The 47.5 tok/s reference is also what motivated a specific check at long
context: the suspicion that the DFlash2 gain "disappears" against a real
production baseline. At 131k, DFlash2 measured 48.19 tok/s (CUDA) and 45.51
(ROCm) — the same order of magnitude as Ollama/MTP, which quantitatively
supports that suspicion, while the gain against a *pure baseline* remains
positive in every configuration. See
[`performance/consolidated-results.md`](../consolidated-results.md) §2.

## Configuration note

Ollama on this machine is configured **ROCm-only** (`CUDA_VISIBLE_DEVICES=-1`,
`ROCR_VISIBLE_DEVICES=0`, `HSA_OVERRIDE_GFX_VERSION=12.0.1`), so it cannot use
the RTX 3090 Ti. Any Ollama measurement here is on the R9700.

This also has a practical consequence discovered the hard way: running Ollama
while the Lucebox server holds the R9700 does not fail — it silently spills the
model to CPU (observed: 79% CPU / 21% GPU) and contends for the same card.
