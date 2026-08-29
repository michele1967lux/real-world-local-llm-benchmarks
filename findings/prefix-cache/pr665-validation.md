## Independent validation on AMD / ROCm (gfx1201)

We hit this same livelock in a long ds-harness coding session and worked it
through from the source before finding this PR — arriving at essentially the
same root cause and the same fix (`skip_index`, threading the physical restore
slot, `-1` when nothing is safe to evict). Since #665 got there first and is
more thoroughly verified, this is a validation report rather than a competing
patch.

One useful additional data point is that your verification is on RTX 3090s,
while ours is on AMD. **The fix is not incidentally CUDA-specific.**

### Setup

- AMD Radeon AI PRO R9700 (gfx1201, 32 GB), ROCm 7.2.1, Ubuntu 24.04.4, kernel 6.17
- Qwen3.8-27B target (16 GB GGUF) + DFlash2 draft, `--draft-block-size 16`
- `--prefix-cache-slots 4 --max-ctx 32768`, 16 linear turns, tool schema attached
- Your patch applied onto `136ad9c` (clean apply), built and run against the
  unpatched build of the same commit — same machine, same session, back to back

### Results

| | pre-fix | **PR #665** |
|---|---|---|
| restored `prefix_len` past saturation | **frozen at 3072** for all 12 turns | 3072 → 7680, advancing |
| inline snapshots committed / 16 turns | 4 | **14** |
| eviction attempts | 12 | 3 |
| victim chosen | deepest entry, **12/12** | redundant ancestor (`idx=1`) |
| total prefill | 65.2 s | **29.0 s** |
| latency at turn 16 | 8.60 s, climbing monotonically | **2.45 s, flat** |

`test_slide_*` 4/4 and the pre-existing eviction-policy tests 7/7 pass on ROCm.

The protected pin behaves as intended: the log shows
`prefix-aware evict: victim idx=1 ... kept oldest ancestor (len=2016)` — the
system+tools head survives and a redundant ancestor is sacrificed instead.

For what it's worth, we independently wrote a fix with one difference: our
fallback picks the oldest ancestor whose cached descendants all still lie on
the restore chain, rather than the shallowest unprotected one. On this workload
the two are indistinguishable — identical `prefix_len` sequence turn by turn,
same victim, and total prefill within run-to-run noise (29.0 s vs 30.6 s). The
difference only shows up when a side branch is itself pinned, and it is a policy
choice about preserving future divergence points, not a correctness issue. Your
reasoning that the shallowest ancestor's cached prefix is already represented
by deeper snapshots on the same chain holds for this eviction decision.
Mentioning it only in case it is useful.

### One reproducer caveat that cost us a cycle

Our first end-to-end reproducer **passed against the buggy binary**. Ten turns
with small prompts and no tools: only 3 snapshots ever committed against 4
slots, zero evictions — the cache never saturated, so the run never entered the
regime where the livelock lives. A multi-turn test can report a false green
here unless turn size and tool schema are tuned so `--prefix-cache-slots` is
genuinely filled well before the run ends.

We made both explicit parameters for that reason. Happy to contribute the
script separately if a regression guard of that shape is wanted — it asserts
that the restored `prefix_len` never regresses and advances at least once over
the turns past saturation. (That invariant is a property of strictly-extending
prompts, not of the server in general: a changed template, tool set, or a real
branch may legitimately shrink the reusable prefix.)

Thanks for the fix — it takes a real coding-agent session from unusable back to
usable on this hardware too.
