# Coding agent benchmarks

Two tasks assigned to the local coder, judged independently.

| | Compaction extraction | Durable job queue |
|---|---|---|
| type | high-fidelity port of an existing module | greenfield, from scratch |
| source to respect | yes (`deepseek-harness`, MIT) | none |
| candidates | Qwen3.8 **and** Claude Code | Qwen3.8 only |
| outcome | **59** against **87** | **PASS with 2 defects** |
| independent judge tests | 22 differential scenarios | 17 adversarial tests |

## The two outcomes are not the same scale

The first compares two candidates on the same task: the 59 is **relative**. The
second has a single candidate: the PASS is **absolute**. Lining them up as a
single ranking mixes two different axes — task type and the presence of a
comparator.

The hypothesis that emerges from this — *Qwen3.8 more competitive at greenfield
design than at high-fidelity porting* — is plausible but **not yet
supportable**: one task per category, no comparator in the second, and
different judges.

## The most informative data point is not the score

It is the **evolution of the error class**.

In the first benchmark, `PLAN.md` declared five features that **did not exist
at all** in the code — findable with a `grep`.

In the second, the implementation is largely correct, but `DECISIONS.md`
declares an **emergent property** that the system does not produce: it claims
three times that incrementing `attempts` at claim time limits the total
executions and drives to `dead` a job whose worker always dies. Falsified by
running the scenario: 12 claims with `max_attempts=3` give `attempts=12` and
the job stays claimable forever.

The second error is substantially more sophisticated: half of the mechanism is
implemented, and the documentation declares the whole property.

**The residual weakness is the same in both**, shifted up a level: the fidelity
of what the model declares, not the ability to write working code.

## Judgment method

In neither of the two cases was the judgment based on the tests written by the
candidate.

For the port: rebuild and **run the original** against the same external
harness as the candidates. That is how three behavioral divergences emerged
that inspection of the code did not show.

For the greenfield: write **adversarial tests against the specification**,
without reusing the candidate's fixtures, and verify installation from an
external venv and the CLI from the installed entry point.

See `findings/methodology/measurement-errors.md` §M10.
