# Coder comparison: Qwen3.8/Lucebox vs local "Sonnet 5" (deepseek-harness)

Primary sources (sister repo `deepseek-harness/`, **read-only**):
`extracted-compaction-rocm-qwen27b/{TASK,PLAN,ROADMAP,PROGRAM_STATE}.md`
(read in full for this report) and `extracted-compaction-sonnet5/`
(see the note on the compromised source, below) — plus the summary already
recorded in `PROGRAM_STATE.md` §"Backend 'sonnet5' per confronto qualità
coder" of this same repo.

## Important note on the "sonnet5" source — incident and limitation of this report

While this comparison was being written, a sub-agent of the session
**wrote by mistake** inside
`deepseek-harness/extracted-compaction-sonnet5/` (outside its own
scope, which was supposed to be read-only), overwriting that folder's
`PLAN.md`/`ROADMAP.md`/`PROGRAM_STATE.md`/`src/*` with unrelated
content (a generic project scaffold: `package.json`,
`tsconfig.json`, `vitest.config.ts`, `src/` files not pertinent to the
compaction extraction task). The incident was detected by the Claude Code
coder that actually owns that folder (an independent instance,
mid-execution), reported, and the erring agent was stopped by Lux before
it could cause further damage. `extracted-compaction-sonnet5/` does not
belong to this reporting work: it belongs to another independent agent that
is actually executing the task, in parallel, as the A/B point of comparison.

Consequence for this file: **the current on-disk content of
`extracted-compaction-sonnet5/{PLAN,ROADMAP,PROGRAM_STATE}.md` is not
trustworthy** (it is the result of the overwrite, not the original work
of the "Sonnet 5" coder) and **it was not used as a source here**. Lux is
restoring the original content separately, from a copy he already has in
hand; repairing it is not the job of this reporting. Until the restore is
confirmed, the comparison below is limited to:

1. Qwen-side data, verified today in full (intact source, read
   directly);
2. the planning-phase-only comparison already recorded **before**
   the incident in this repo's `PROGRAM_STATE.md` (dedicated section,
   quoted below) — the only "sonnet5" evidence considered trustworthy at
   the time of writing.

A deeper comparison (implementation phase: `src/*`, test
coverage, faithful adherence to the real source code) on the sonnet5 side
**was not attempted** — it would have been built on corrupted data and
therefore invalid by construction. It must be redone after the restore, as
an update to this file.

## What the common task is

Both coders (Qwen3.8-27B via the Lucebox backend, and a local Claude Code
instance — "Sonnet 5", **not** the Anthropic API, no paid
dependency) received the **exact same `TASK.md`**: extract the DeepSeek
Harness compaction system
(`packages/compaction/{compaction,compaction-basic}/`) into an isolated
TypeScript module, importable and testable without Cordis, with the same
governance rules (PLAN/ROADMAP/PROGRAM_STATE mandatory before writing
code, one phase at a time, no silent stubs, fidelity to the source with
divergences declared explicitly before writing them).

Verified today by direct diff: the `TASK.md` of the two folders is
identical apart from the name of the destination folder cited inside it
(`extracted-compaction-rocm-qwen27b` vs `extracted-compaction-sonnet5`) —
no other difference. The A/B comparison is therefore on the exact same
mandate.

## Qwen3.8/Lucebox side (`extracted-compaction-rocm-qwen27b/`) — intact data

State read today, in full, directly from the files (no corruption
observed on this side):

### Deliberate divergences from the source (D1–D7), from `PLAN.md`

None of them alters the compaction logic; each one is declared **before**
writing the corresponding code (compliance with the governance rule):

| # | Divergence |
|---|---|
| D1 | No Cordis: `CompactionEngine` does not extend `Service`; `CompactionEventMap` becomes a local type |
| D2 | `dsh-llm` vocabulary redefined to the bare minimum (only the fields compaction reads); `BlockAssembler` ported in a minimal version |
| D3 | Cordis event wiring (`agent/pre-step`, `agent/request-error`, `agent/status`, `session/event`) exposed as callable methods of the engine, with the same guards as the source |
| D4 | External dependencies (tokenMeter, llm, sessions.flush, pruner, logger) injected via minimal interfaces |
| D5 | Companion pruner (optional in the source) not extracted; `compaction/prune` event kept in the map for protocol fidelity |
| D6 | Config validation ported in full (already runtime-pure in the source, no `zod`/Schemastery dependency to replace) |
| D7 | `facade.ts` new, a typed operational layer (no `any`) with no 1:1 counterpart in the source, declared as such |

### Phase progress, from `ROADMAP.md` + `PROGRAM_STATE.md`

| Phase | Content | State |
|---|---|---:|
| 0 | Governance (PLAN/ROADMAP/PROGRAM_STATE) | Complete |
| 1 | Foundations without Cordis (`brand.ts`, `session.ts`) | Complete — 21/21 tests |
| 2 | Seam: vocab, checkpoint, tool-pairing | Complete — 60/60 tests (5 files) |
| 3 | Range and transaction | Complete — 72/72 tests (7 files) |
| 4 | Summarizer | Complete — 81/81 tests (8 files), last log entry 2026-08-28 19:18 UTC |
| 5 | Engine (`BasicCompactionEngine`) | Not complete as of the reading date (checklist not ticked in `ROADMAP.md`) |
| 6 | Facade, public surface, closing | Not complete as of the reading date |

Verification declared at every phase: `tsc --noEmit` (strict) + `vitest run`,
both green before marking a phase as done — no open "TODO(governance)"
recorded in phases 0-4.

## "Sonnet 5" side — only what was already recorded before the incident

From this repo's `PROGRAM_STATE.md` (section "Backend 'sonnet5' per
confronto qualità coder", written before today's overwrite):

> Preliminary result (only the planning phase compared so far):
> both converge on the same 7 deliberate divergences from the source
> (D1-D7) — a signal that the scope-reduction choices are dictated by the
> source, not arbitrary. Sonnet 5 slightly more granular in the
> breakdown of the phases and in the function-level citations from the
> source; no substantive difference in the understanding of the original
> code.

Points that this summary allows to be stated with confidence:

- **Convergence on D1-D7**: the two coders, independently, arrived
  at the exact same 7 divergences from the real source
  (Cordis removed, minimal vocab, event wiring exposed as methods,
  dependency injection, pruner not extracted, config ported in full, new
  facade). Since these are independent choices converging on the same
  exact set, it is a signal that the divergences really are imposed by the
  source (coupling to Cordis, etc.) and not an individual coder's arbitrariness.
- **Qualitative difference observed**: slightly greater granularity
  in the breakdown of the phases on the Sonnet 5 side and more precise
  citations at the function level — no substantive difference in the
  understanding of the source.

What can NOT be stated here: the real progress of the implementation
phases (1-6) on the Sonnet 5 side, test counts, the outcome of
`tsc --noEmit`/`vitest run`, coverage of D1-D7 in the actual code — those
data require reading
`extracted-compaction-sonnet5/{ROADMAP,PROGRAM_STATE}.md` and `src/*`, and
that is exactly the content compromised by the incident described above.

## Outcome — resolved after this chapter was written

The three steps set out below were **carried out**, along a different path
from the one hypothesized: instead of restoring the compromised folder, the
Sonnet 5 side was **re-executed from scratch** in a clean environment, with a
single isolated agent and with no access whatsoever to Qwen's work. Duration:
30.6 minutes (23:06:02 → 23:36:37, from the timestamps of the agent's own
transcript; the framework's `duration_ms` agrees).

The comparison was then judged independently, by reconstructing and
**executing the original** against the same external harness as the two
candidates, instead of merely reading its code. Outcome: **Sonnet 5 87,
Qwen3.8 59**. The Qwen candidate was not importable as delivered
(`ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX`), showed 3 confirmed behavioral
divergences, and its `PLAN.md` declared five features that did not exist in
the code.

**A second, greenfield benchmark** was run the next day on the
same stack: building a durable job queue on SQLite from scratch. The
opposite outcome — **PASS**, with 53/53 of the candidate's tests and 17/17
independent adversarial tests passed. See [`coding-agents/durable-job-queue/`](../durable-job-queue/)
for the task, manifest and judge report, and [`coding-agents/README.md`](../README.md) for
the comparison between the two benchmarks and — importantly — for the
**confounders that do not yet make sustainable** the conclusion "Qwen is
stronger in greenfield than in porting".

## Correction to a timing figure quoted elsewhere

A duration of "~57 min" was circulating for the Sonnet 5 side, derived from
the mtimes of the folder's files. It is **inflated**: the first file
(`TASK.md`, 22:39) is the folder reset done by the coordinator, not work by the
agent, which started at 23:06. The `TASK.md` → last file method adds ~15 min on
a total of 10.6 h for Qwen (irrelevant, 2%) but 33 min on 30 of real work
for Sonnet (it doubles the value). The same method applied at two scales
produces an asymmetric systematic error.

The clean figure is **30.6 min**, measured directly on the agent's
transcript. For Qwen no equivalent exists — it is an external ds-harness
session, with no per-agent transcript — and that is why no exact "active
time" is published for that side in `PROGRAM_STATE.md`.
