# Language and preservation policy

## Canonical documentation is English

README, analyses, judge reports, benchmark descriptions, manifests and
contribution guidelines are written in English. There is no full EN/IT
mirror: duplication doubles maintenance and invites divergence.

## Experimental artifacts are preserved verbatim

The following are **never rewritten, translated, or tidied retroactively**:

- original task specifications, exactly as delivered to the candidates;
- candidate outputs, including their `FINAL_REPORT` and governance documents;
- the judged Git history of a submission;
- raw logs and raw result files.

Translating an experimental input would create a prompt the candidates never
received. Editing a candidate's output would destroy the thing being
evaluated.

Where an artifact is in another language or in a form that needs context, we
add a **clearly separated editorial note** at the top — never an edit to the
body.

## Retractions are not cleaned up

Analytical documents keep the sequence:

```
initial conclusion
→ what later invalidated it
→ corrected conclusion
```

Superseded conclusions are marked as superseded, with a pointer to the current
one. They are not deleted. A repository that only shows the conclusions that
survived is less useful, and less trustworthy, than one that shows how they
were reached.

## One canonical source per fact

If a number or a finding appears in two places, one of them is a pointer. Old
files are not kept "for completeness" when they restate the same events with
earlier numbers or superseded conclusions.
