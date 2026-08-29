# R9700 idle power — ~70 W burned doing nothing

## Upstream status

Two issues describe this on exactly this hardware. Both were **transferred** to
`ROCm/legacy-rocm-build` and both are **closed as completed**:

| | opened | closed | comments |
|---|---|---|---|
| [legacy-rocm-build#5706](https://github.com/ROCm/legacy-rocm-build/issues/5706) — HIP backend in llama.cpp keeps RDNA4 (gfx1201 / R9700) at 100% after idle | 2025-11-27 | 2026-03-18 | 36 |
| [legacy-rocm-build#6298](https://github.com/ROCm/legacy-rocm-build/issues/6298) — PyTorch ROCm resident process keeps R9700/gfx1201 at 100% idle until process exit | 2026-05-25 | 2026-06-25 | 6 |

**Closed does not mean fixed here.** After the closure of #5706, a user
reported (2026-04-02) still seeing 100% GPU usage on **ROCm 7.2.1** — our exact
version — on a 6.17 kernel. Our measurements below are on ROCm 7.2.1 and are
consistent with that report.

We have not filed anything upstream: the issues are closed, and re-opening
someone else's thread to add one more data point is not obviously useful. The
measurements are published here instead.

## What we measured

Reproduced on a single R9700 with a llama.cpp-derived HIP server (Lucebox
`dflash_server`). Worth recording because the setup differs from the original
report (one GPU instead of three, newer ROCm) and because the trigger condition
turned out to be narrower than "process is running".

**Setup:** AMD Radeon AI PRO R9700 (gfx1201), amdgpu 6.16.13, ROCm 7.2.1,
kernel 6.17.0-40, Ubuntu 24.04.4. Server holds 6 resident HSA queues and one fd
on `/dev/kfd`.

**Four states measured on the same machine, same session:**

| state | `gpu_busy_percent` | `mem_busy_percent` | core clock | power | junction |
|---|---|---|---|---|---|
| no server process | 3–9% | 0–1% | 41–1435 MHz, varying | **22–36 W** | 67 °C |
| server up, model resident, **no request served yet** | 1–6% | 0–1% | 6–1526 MHz, varying | **18–31 W** | 56 °C |
| server idle **after** serving requests | **100, constant** | 0–4% | **3441 MHz, pinned** | **93–105 W** | 80–82 °C |
| server under real load | 100 | 53% | 3061 MHz | 291 W | 110 °C |

**The detail I did not find in the thread:** a freshly started server that has
loaded the model into VRAM but has not yet served anything does *not* show the
stuck state — 1–6% busy, 18–31 W, clocks still ramping freely. The pin appears
only after the first real generation. So the trigger looks like HIP work rather
than merely having an initialised runtime with queues resident, which may narrow
where to look in queue creation vs. teardown.

**One caveat on my own observation, so nobody over-reads it:** in a later
session I caught a single sample at 3% busy / 34 W / 1557 MHz during a short
gap between requests, on a server that had been generating for a long time —
then it went straight back to a stable 100% over the next six samples. So the
pinned state is what I see sustained, but it is not absolutely permanent within
a process lifetime, and I cannot yet characterise what makes it release. Pause
length does not explain it: a long idle period earlier stayed pinned at 100%,
while this short gap did not. Treat the "persists until process exit" part as
what I observed, not as a rule I have established.

**Cost:** stopping the process drops the card from ~95 W to ~25 W, about 70 W,
so roughly 1.7 kWh/day for a server left resident but idle. Consistent with
this being a real power-state problem rather than a reporting artifact.

**Sampling note for anyone else measuring this:** in the stuck state
`gpu_busy_percent` reads exactly 100 with zero variance across samples, while
`mem_busy_percent` and power keep fluctuating normally. Under genuine load it
also reads 100 but `mem_busy_percent` goes to ~53% and power to ~291 W. So
`gpu_busy_percent` alone cannot distinguish the two — `mem_busy_percent` and
power draw can.

I have not tried `GPU_MAX_HW_QUEUES=1` or `sched_policy=2` on this machine;
this is a production box and I did not want to change module options under it.
Happy to run a numbered before/after if a specific configuration would be
useful.
