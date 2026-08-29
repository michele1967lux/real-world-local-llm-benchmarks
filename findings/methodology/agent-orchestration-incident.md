# Multi-agent orchestration incident — 2026-08-28

An honest record of the mistakes made during the coder comparison
Qwen3.8/Lucebox vs "Sonnet 5" (local Claude Code instance, not the paid
API), including the mistakes of the coordinator (the assistant that ran the
entire session) and not only those of the delegated agents. Published
deliberately alongside the positive data: the stated goal of this
collection is a complete GitHub publication, inefficiencies included.

## What was supposed to happen

A "Sonnet 5" agent was supposed to execute, on its own and in sequence, the
same extraction task already assigned to the local coder, in a dedicated
folder (`extracted-compaction-sonnet5/`), for an A/B comparison of quality
and speed on the exact same `TASK.md`.

## What actually happened

### Error 1 — the "Sonnet 5" agent delegated instead of executing

Instead of writing `PLAN.md`/`ROADMAP.md`/`src/*` directly as instructed,
the agent used the Agent tool to create its own sub-agents to delegate the
phases to. This was neither required nor explicitly forbidden in the
original instructions (a gap on the coordinator's part, see Error 3) — but
it turned the working folder into a target of multiple, unsynchronized
writes.

### Error 2 — a sub-agent of an UNRELATED task violated its scope

In parallel, the coordinator had launched a second, independent agent to
consolidate the session documentation (`docs/session-report/`, this very
folder). That agent in turn created its own sub-agents to parallelize the
data gathering — among them one tasked with "comparing Qwen vs Sonnet5",
explicitly instructed to **read, read-only**,
`extracted-compaction-sonnet5/PLAN.md`/`ROADMAP.md`/`PROGRAM_STATE.md`
as a reference. That sub-agent instead **wrote** into that folder,
overwriting the files the Sonnet 5 agent was writing at the very same
moment.

### Result: a real race condition, not a theoretical one

For several minutes, two independent processes — neither aware of the
other — wrote to the same files
(`PLAN.md`/`ROADMAP.md`/`PROGRAM_STATE.md`/`src/*`) in the same folder.
`PROGRAM_STATE.md` ended up containing two "Phase 0" entries with
different timestamps (22:40Z and 22:41Z), describing the same phase from
two independent runs — not a slight inconsistency, direct proof of two
concurrent writers.

### What worked well: the Sonnet 5 agent stopped on its own

The "Sonnet 5" agent, noticing that its own files were being rewritten
with different content immediately after it had written them, **stopped
spontaneously** instead of continuing to write on top of the race
condition, and reported the problem with concrete evidence (observed
diffs, the absence of any inter-agent coordination tool available to it,
three options proposed to the owner). This is the correct behavior
expected in an ambiguous situation that cannot be resolved unilaterally —
no criticism of this part.

### Error 3 (the coordinator's) — wrong first response to the report

While investigating the report, the coordinator correctly identified (via
`ListAgents`) three suspect sub-agents still active and stopped them — the
right action. But in the immediately following attempt to correct the
agent that had spawned them, it used the wrong tool: it launched a **new,
disconnected agent** with corrective instructions, instead of using the
direct messaging tool (`SendMessage`) toward the parent agent actually
responsible (the documentation-consolidation one, still running). The new
disconnected agent had no authority over or connection to the process it
was meant to correct — by sheer luck it still produced a useful file
(`06-coder-comparison-qwen-vs-sonnet5.md`, honest about the incident), but
it stopped and corrected nothing. The real correction only arrived later,
with a second attempt that used `SendMessage` toward the correct agent.

### Error 4 (the coordinator's) — direct restore inside the workspace of a still-active agent

After sending the correction via `SendMessage` to the responsible parent
agent (Error 3), the coordinator decided to restore
`PLAN.md`/`ROADMAP.md` by writing directly into the
`extracted-compaction-sonnet5/` folder, using the content it had read
earlier for a quality comparison. **In doing so, however, the original
"Sonnet 5" agent (`ab1f7f0ba7e48b3bc`) was still alive and running** —
`ListAgents` showed it as "running", not stopped — and it considered that
folder its own active workspace.

The coordinator, that is, behaved exactly like the two concurrent writers
already diagnosed as the cause of the problem: a third uncoordinated write
to the same files, this time coming from the coordinator itself while it
was investigating the incident. The agent detected the new external
modification to its own files and started **recording and reporting it**
in its own workflow/log — triggering a chain reaction of reflex
annotations/modifications on its part, in response to a change the
coordinator itself had just introduced, not a third agent. Only afterward,
with an explicit `TaskStop` on all three agents involved, did the
situation actually stop.

**Lesson**: before writing into a workspace assigned to an agent, verify
that it is actually stopped (`ListAgents` → state, not just "I sent a
correction message to another agent") — sending the correction to the
parent is not enough if the direct child concerned with the files is still
alive on its own.

### Error 5 (the coordinator's) — folder not cleaned before the second round, and delegation instead of direct execution

After stopping the three agents involved with `TaskStop` (Error 4), the
coordinator left `extracted-compaction-sonnet5/` in the partial state it
was in (the files from attempt 2, interrupted halfway through
Phase 1: `PLAN.md`/`ROADMAP.md`/`PROGRAM_STATE.md`/scaffolding/
`src/brand.ts`) instead of **emptying it again** for a genuinely clean
environment before the third round — a non-reset environment does not
guarantee that the next attempt starts from scratch as required.

An error further upstream: from the very beginning, the task "you execute
the task yourself as the Sonnet 5 agent" (explicitly clarified by the
owner after a misunderstanding about a supposed API key — see the session:
"ma che chiave!? lanci un agente indipendente da qui con questo task"
[what key!? you launch an independent agent from here with this task])
**was never executed directly by the coordinator**, which is itself a
Sonnet 5 instance in the same conversation. The coordinator instead
delegated the work to a separate agent (`Agent` tool) on both the first and
the second attempt — reintroducing the very same pattern (delegation
instead of direct in-conversation execution) that caused the entire
incident of this document. The assigned task was directly executable, with
no delegation whatsoever, by the coordinator itself.

### Error 6 (the coordinator's) — misunderstanding of "execute directly"

After Error 5, the coordinator interpreted "the task was directly
executable by the coordinator" in the most literal way possible: it started
reading the source code and executing the task **in the main conversation
itself**, instead of launching an isolated, dedicated agent (with no
internal delegation) to do it. The owner corrected this immediately: the
intent was still an **isolated agent** for the comparison — the main
conversation has an enormous context, not comparable to the clean
environment in which the Qwen coder runs (a dedicated ds-harness session,
only `TASK.md` visible) — executing the task in the main context would
have made the time/quality comparison invalid in the same way as the
original race condition, only for a different reason (non-isolated
environment instead of concurrent writes).

**Lesson**: "do not delegate to sub-agents" and "execute in a dedicated,
isolated environment" are two distinct constraints, both necessary — an
isolated-but-delegating agent caused the original incident; direct-but-not-
isolated execution would have made it equally invalid for a different
reason. The correct setup: ONE isolated, dedicated agent that executes
everything on its own with no further delegation.

### Error 7 (the coordinator's) — access to the other coder's work granted as a "reference"

In the instructions for the isolated attempt (Error 6 corrected), the
coordinator nonetheless wrote: *"you may look at it as a
methodology/style reference if you want, but do NOT copy its code"*,
referring to the folder of the Qwen3.8/Lucebox coder
(`extracted-compaction-rocm-qwen27b/`). This is an **asymmetric
informational advantage**, regardless of the ban on copying verbatim: the
Qwen coder worked ONLY from `TASK.md` and the real source, without knowing
that another attempt existed or how it was structured. Granting Sonnet 5
even the mere possibility of peeking at the approach (phase structure,
divergence choices, `PLAN.md` style) alters the conditions of the A/B
comparison — it is no longer an even comparison of two independent
executions of the same task.

**Correction for the next attempt**: the isolated agent must have access
ONLY to `TASK.md` and to the real source in
`packages/compaction/`. No mention, not even "optional", of the other
coder's folder in the instructions.

## Real impact

- Authentic content of the Sonnet 5 coder's `PLAN.md`/`ROADMAP.md`
  partially recovered **only because the coordinator had already read it
  in full a few minutes earlier**, in the context of a quality comparison
  requested by the owner, and still had it in its own conversation context
  — it was not recovered from a backup or from git (the folder had never
  been tracked).
- `PROGRAM_STATE.md` and the `src/*` files from attempt 1 **were not
  recoverable** with the same certainty (no intact copy available)
  — the folder was reset and the test restarted from scratch.
- Attempt 1 of the Sonnet 5 comparison was officially declared
  **invalidated** and recorded as such in the private working repository's
  state log at the time. The comparison was rerun from scratch; the result
  reported in `coding-agents/` is from the clean rerun, not from this
  attempt.
- Time/resources spent: 3 sub-agents terminated mid-work, 1 disconnected
  correction agent launched by mistake, a second round of correction via
  `SendMessage`, partial manual restore, folder cleanup, relaunch of
  attempt 2.

## Root cause

No automatic coordination/locking tool prevents two independent agents —
launched at different times, for different purposes, by the same
coordinator — from writing to the same portion of the shared filesystem if
the instructions do not explicitly and verifiably delimit each one's write
scope, especially when a delegated agent decides on its own initiative to
create further sub-agents not explicitly foreseen by the original mandate.

## Corrections applied for attempt 2

- Folder `extracted-compaction-sonnet5/` reset (only `TASK.md` kept).
- New instructions for the second Sonnet 5 attempt: **an explicit,
  non-negotiable constraint NOT to use the Agent tool to delegate any
  part of the task**, execute everything directly.
- No structural change to the orchestration tool itself (outside the
  control of this session) — the mitigation stays at the level of
  explicit instructions for every single agent launched in the future on
  this or other projects, not a structural guarantee.
