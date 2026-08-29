# System RAM exhaustion — a default that only bites under real load

A configuration defect that no fixed-prompt benchmark could have surfaced: it
only appears in a long agent session, and it nearly took the machine down on
the first real end-to-end run.

## The problem

`scripts/serve-lucebox.sh` was not passing `--prefix-cache-slots` to
`dflash_server`, so the binary used its **native default of 32 slots**.

Each slot holds a complete KV snapshot in **system RAM**, not VRAM — visible in
the log as `[snap] alloc ... backend=CPU` — and each snapshot grows with
context depth. One snapshot was observed at **~2.76 GB at ~72k tokens** of
context.

During the first real end-to-end ds-harness run, system RAM climbed to
**37 GB used out of 39 GB (376 MB free, swap being touched)** before a manual
stop. Filling all 32 slots would have exceeded the 39 GB available.

## The fix

`--prefix-cache-slots` is now passed explicitly, defaulting to **4**
(overridable via the `LUCEBOX_PREFIX_CACHE_SLOTS` environment variable).

Four is the minimum value Lucebox's own `server/docs/TOOL_PREFIX_CACHE.md`
recommends ("Start the production server with at least four prefix-cache
slots").

## Two source claims that had to be checked, and one that was wrong

**The native default really is 32**, confirmed three ways: `--help`,
`http_server.h` (`prefix_cache_cap = 32`), and `TOOL_PREFIX_CACHE.md`. A table
in Lucebox's `DEVELOPER.md` stating "4" is **stale documentation**.

**A proposed explanation was rejected as wrong**: the hypothesis that an
environment variable `DFLASH_PREFIX_CACHE_SLOTS=32` was the cause. That
variable is read only by Lucebox's `server/scripts/entrypoint.sh`, used for
containerized launches — never by the native binary that `serve-lucebox.sh`
starts directly.

## Verified in production

Across the ~90-turn session, available RAM stayed between **~18 GB and ~31 GB**
in the worst phases, never near the critical threshold. The claim was promoted
from `assumed` to `VERIFIED`.

## Related experiment: `--prefill-cache-slots`

A second, separate cache tier ("Tier 2", exact full-prompt matches rather than
growing prefixes), native default 0, was tried at 2.

| | Before (without, 78 turns) | After (with, 53 turns) |
|---|---:|---:|
| mean decode | 45.2 tok/s | **57.4 tok/s** (+27%) |
| median decode | 44.4 tok/s | **56.3 tok/s** (+27%) |
| decode min–max | 25.6 – 72.7 | 21.4 – 92.7 |
| standard deviation | 9.5 | 15.3 |

**Declared level: `assumed`, not `VERIFIED`.** The "after" sample includes a
cold-cache restart and shows more variance; the median improvement repeated
across two separate checks (at 34 and 53 turns) but was **not isolated from
other session factors**. Confirming it would need a clean warm-cache cycle,
which was never run.

This is reported as an unresolved experiment, not as a result.

## Why this matters beyond one flag

A default tuned for one deployment shape (containerized, presumably with more
RAM) is dangerous in another. The failure mode is not a crash on startup — it
is a slow climb that only manifests once context grows deep enough, in a
session long enough, which is exactly the regime a fixed-prompt benchmark never
enters.

The same theme recurs throughout this repository: see
[`findings/methodology/measurement-errors.md`](../methodology/measurement-errors.md)
§M3 and §M4.
