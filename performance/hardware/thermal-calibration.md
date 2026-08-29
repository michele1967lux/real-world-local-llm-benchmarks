# Thermal thresholds on the R9700 — recalibrating an alarm that was wrong

Our first monitoring threshold was too aggressive and would have flagged a
healthy card as faulty. This documents the correction and the empirical check
that supports it.

## What we had wrong

**Old threshold**: edge/junction delta > **25 °C** = alarm.

This treats the junction sensor as if it should track the edge sensor closely.
It should not. Junction is a **hotspot** reading — the maximum across many
on-die sensors — not an average. A 30–40 °C delta under load is normal for
this card.

## Corrected threshold

Alarm only when **either**:

- delta > **45 °C sustained** (multiple consecutive readings), **or**
- clock and power **falling** while junction stays high.

The second condition is the one that actually matters. A high delta on its own
is a hot card doing work. A high delta *together with* dropping clocks and
power is thermal throttling, which is what a degraded thermal interface looks
like.

## Reference data

From a public comparative benchmark of a healthy card against one with a
thermal-interface-material defect:

| | healthy R9700 | TIM-defective card |
|---|---|---|
| edge | 70 °C | — |
| junction | 108 °C | — |
| delta | 38 °C | **~47 °C** |
| clock / power | 3171 MHz / 294 W | **reduced simultaneously** |

The defective card is identified by the **combination**, not by the delta
alone.

Source as cited in our notes: "AMD sensor design doc + public comparative
benchmark healthy/defective TIM card, `daimonionnn/amd-r9700-vllm-and-tuning-toolkit`".
**Only the `owner/repo` slug is recorded, no full URL**, and no second
reference with an explicit URL was found. Treat the attribution as
incomplete.

## Empirical check on our own card

From `gpu-monitor.csv`, 106 rows, 2026-08-28 11:51:08 → 14:30:01, restricted
to active rows (`util > 0`, n=99):

| | delta (junction − edge) |
|---|---|
| min | 3 °C |
| max | 42 °C |
| mean | 28.9 °C |

Only 4 rows exceed 40 °C (12:40, 12:41, 12:42, 12:51 — 41–42 °C). All four show
**normal clock and power** (2966–3091 MHz, 248–329 W). **No correlation with
falling clock or power**, consistent with a healthy card.

**Discrepancy declared**: this range (3–42 °C) differs slightly from the
"25–43 °C" cited in our own earlier notes — possibly a different sampling
window. Not resolved.

## The recalibration is documentation, not code

`gpu-monitor-cron.sh`, the script that produces the CSV, is purely a logger
over `rocm-smi` and `journalctl -u ollama`. It contains **no threshold or
alarm logic at all**.

The recalibration described here is therefore an observational policy, not
something enforced by an executable check. A later session monitor did
implement these thresholds, but the historical CSV was produced without them.

## Values observed under real agent load

For reference, during a real coding session on this card:

| | |
|---|---|
| edge | 67–73 °C |
| junction | 94–110 °C |
| delta | 27–41 °C |
| power | 225–315 W |
| clock | 2640–3250 MHz |

Junction touched 110 °C repeatedly with clock and power at full value — hot,
but within the envelope, and not the fault signature.
