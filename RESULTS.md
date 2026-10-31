# Results

Every number here comes from a file in [`proof_results/`](proof_results/). All renders are real YouCam AI Clothes output on synthetic models and garments.

## Totals

From `matrix.json` and `summary.json`.

| | Pass | Warn | Fail | No render | Total |
|---|---|---|---|---|---|
| All | 32 | 3 | 13 | 0 | 48 |
| Long garments | 8 | 3 | 13 | 0 | 24 |
| Short garments | 24 | 0 | 0 | 0 | 24 |

The demo pair on one model (m2_studio): long wool coat refused, covering 59.3% of a wheel; cropped jacket passed, covering 0%.

## Refused renders

All 13 were refused for wheel clearance. Worst-wheel coverage:

| Model | Garment | Covered |
|---|---|---|
| m3_home | Maxi dress | 81.0% |
| m5_outdoor | Maxi dress | 62.3% |
| m2_studio | Long wool coat | 59.3% |
| m6_side | Maxi dress | 50.2% |
| m2_studio | Maxi dress | 48.75% |
| m3_home | Long wool coat | 48.05% |
| m4_home | Maxi dress | 40.7% |
| m3_home | Trench coat | 31.9% |
| m1_studio | Maxi dress | 28.7% |
| m4_home | Long puffer coat | 21.4% |
| m4_home | Long wool coat | 19.8% |
| m2_studio | Trench coat | 19.1% |
| m1_studio | Long wool coat | 15.5% |

Three of these also had a second finding. On m2_studio's long wool coat, the hand check warned. On the maxi dress for m2_studio and m3_home, chair similarity warned (0.665 and 0.672).

Warned, for a person to look at: long puffer on m2_studio (7.5%) and m3_home (12.7%), trench on m4_home (7.0%).

## What this does not show

- Passing means the picture passed these checks, not that the garment is safe to wear in a wheelchair. Some long coats passed because they hang between the wheels in that pose.
- The wheel regions are hand-marked for the six sample photos, so the wheel and chair checks do not run on uploads.
- Thresholds were tuned on the same 48 renders. There's no held-out set, and no wheelchair user has reviewed the results.
- Clearance is a 2D picture measure, not a physical one.

## Planted failures

From `planted_failures.json`. Each kind of damage was applied to each of the 24 short-garment renders. Examples are in `planted/`.

| Plant | Must be caught by | Caught |
|---|---|---|
| None (clean render) | Should pass | 24 of 24 |
| Chair painted out | Wheelchair intact | 24 of 24 |
| Wheels covered | Wheel clearance | 24 of 24 |
| Garment unchanged | Garment applied | 24 of 24 |
| Face altered | Face and hands | 24 of 24 |
| Hand altered | Face and hands | 24 of 24 |

The hand result is not independent: on its first run, 14 of 24 were caught, and the hand limit was then raised using that same set (see below). A test in `tests/test_checks.py` repeats the plants on three renders each time the suite runs.

## How the thresholds were set

From `threshold_history.json`, `summary.json` and `planted_failures.json`.

The first values gave 20 pass, 14 warn, 14 fail. Doubtful cells were then compared by eye with their source photos, leading to three changes:

1. **Garment applied.** Five real try-ons warned because the new garment was close in colour to the old clothes. Pass moved from 0.04 to 0.01 of the picture and fail from 0.01 to 0.003. The smallest real change is 0.011.
2. **Hand scoring.** A render was refused because a sleeve correctly covered a wrist. Hands are now scored only on pixels the garment does not cover.
3. **Hand fail limit.** Moved from 0.40 to 0.55. The lowest real hand score is 0.643.

Unchanged from the first values:

- **Wheel clearance:** pass under 0.05, fail from 0.15. The highest short garment is 0.0469. The warn band holds 0.0698, 0.0754 and 0.1269, and the lowest refusal is 0.1549.
- **Chair similarity:** pass 0.80, fail 0.65. The lowest real score is 0.665, so no real render failed on this check, only warned.
- **Face similarity:** pass 0.80, fail 0.60. The lowest real score is 0.847.

## Automatic wheel finding: failed, turned off

From `locator_eval.json`. Against the hand marks, it found 2 of 23 wheels and returned 15 false positives. Scoring uploads against wrong regions would be worse than not scoring them, so uploads report the wheel and chair checks as "not measured" and can't reach a full pass.

## API use

From `summary.json` and `youcam_calls.jsonl`.

- 50 tasks in the ledger, against a build limit of 120. 49 succeeded, none reported failure, and no error codes were recorded.
- The other task is a hand-written correction row: a logging bug raised an error straight after a task was created, so its result was lost. It's counted because it was probably charged.
- One of the 49 is the real upload run through the app's own route (`live_path_check.json`): verdict warn, wheel checks not measured, face and change passed.
- Dollar spend isn't known, because the ledger holds no prices.

## Accessibility

From `accessibility.json`. Axe (WCAG 2.0 and 2.1, A and AA) found 0 violations on the shopper, retailer and how-it-works views at 1280 and 390 pixels wide, with no sideways scrolling. The keyboard walk opened and closed the detail dialog and changed the garment with arrow keys. Screenshots are in `screens/`.
