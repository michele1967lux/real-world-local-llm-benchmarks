# Hardware

All the measurements in this repository come from a single machine.

| | |
|---|---|
| CPU | AMD Ryzen 9 3950X (16c/32t) |
| RAM | 39 GB usable |
| GPU 1 | **AMD Radeon AI PRO R9700** — gfx1201 (RDNA4), 32 GB, PCIe |
| GPU 2 | **NVIDIA GeForce RTX 3090 Ti** — 24 GB |
| OS | Ubuntu 24.04.4 LTS |
| Kernel | 6.17.0-40-generic |
| ROCm | 7.2.1 |
| amdgpu | 6.16.13 |

The two GPUs are in the same host but are **never used together** for a
single model: no cross-GPU split. The ~18 GB quantized model fits comfortably
in a single card, and keeping the backends separate makes the CUDA/ROCm
comparisons direct.

## Mutual exclusion constraint

The llama.cpp ROCm backend and Lucebox share the same physical GPU: they
cannot run at the same time. The startup scripts check this over HTTP and
refuse to start if the other one answers.

## Note on the kernel

The kernel is deliberately held at 6.17: HWE 7.0 was removed because
`amdgpu-dkms` does not compile. To be reconsidered when ROCm supports 7.0.

## Note on the power profile

During part of the measurements the R9700 was kept in the `COMPUTE` profile
with `power_dpm_force_performance_level = manual`. This does **not** affect the
throughput results reported: the comparison between profiles is documented in
`performance/hardware/rocm-idle-power-gfx1201.md`, which shows that the clocks
stayed pinned even in `POWER_SAVING` because of a runtime bug.
