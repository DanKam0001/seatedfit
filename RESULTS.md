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
- The saved matrix uses wheel regions marked by hand on the six sample photos. Uploads use the shopper's own marks, measured below.
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

From `locator_eval.json`. Against the hand marks, it found 2 of 23 wheels and returned 15 false positives. Scoring uploads against wrong regions would be worse than not scoring them, so the shopper marks each wheel instead. With no marks, uploads report the wheel and chair checks as "not measured" and can't reach a full pass.

## Wheels marked by the shopper

From `marked_wheels_proof.json`, `marked_wheels_sample.json` and `marked_wheels/`. One sample photo (m2_studio) was sent down the upload path through the real marking control in a browser: one mark by mouse, one by keyboard, two by slider. The marks were read by eye off the photo, and `regions.json` was not used.

| Run | Long wool coat | Cropped jacket |
|---|---|---|
| Upload path, fresh paid render, marked wheels | Refused, 61.26% of a wheel | Passed, 0% |
| Sample button, saved render, marked wheels | Refused, 64.35% | Passed, 0% |
| Saved matrix, hand-marked regions | Refused, 59.3% | Passed, 0% |

The verdict matched, but the percentage moves with the marks and the render. `screenshots/06_marked_wheels_result.png`, with slightly different marks and big wheels only, reads 70.5% for the same coat.

### How much marking error matters

From `marked_wheels_eval.json`. Every saved render was rechecked with wheels only, as an upload has, using simulated marks: the eye marks moved at random and resized. Each is compared with the same wheels-only check at no error. No real shopper's marks were measured, and the mark tolerance below was chosen on these same photos.

| Largest move, share of picture | Runs | Same verdict | Refused became passed | Passed became refused |
|---|---|---|---|---|
| 0 | 48 | 48 | 0 | 0 |
| 1% | 192 | 181 | 0 | 0 |
| 2% | 192 | 154 | 0 | 0 |
| 4% | 192 | 96 | 0 | 1 |

Size changed by up to four times the move. A careful hand holds up, but a loose one often changes the verdict, and at 4% half of them did.

A mark must sit on a real outline to earn a pass: within 12 pixels, at least 0.40 of its rim on an edge (`mark_support`). All 11 real wheels clear that, the lowest at 0.417, as do all 12 casters. 6 of 184 marks thrown at places that aren't wheels also clear it, so a stray mark can occasionally get through this test.

## Skin tone and colour contrast

From `feature_cost.json`, `skin_tone.json` and `youcam_calls.jsonl`.

- The feature-cost list gives 20 units for one facial colour reading. One test was spent, and it succeeded first time on a face crop of m2_studio with angle strictness low: skin colour #74523c. The local estimate on the same face is #895946, so the two are visibly apart.
- The endpoint used is `task/skin-tone-analysis`, because that is the one that lists colours in the docs and the cost list. `task/face-attr-analysis` in the brief doesn't.
- The reading also returned a hair colour, which looks unreliable on an upscaled crop, so only skin colour is used.
- The other five samples use the local estimate, because a reading each would have broken this pass's 40-unit limit. The page labels which is which.
- Contrast is CIEDE2000 distance between skin colour and the garment's main colour. It orders the list and nothing else: the check results don't use it.

## API use

From `summary.json` and `youcam_calls.jsonl`.

- 53 tasks in the ledger, against a build limit of 120. 52 succeeded, none reported failure, and no error codes were recorded.
- The other task is a hand-written correction row: a logging bug raised an error straight after a task was created, so its result was lost. It's counted because it was probably charged.
- The 3 newest are the skin tone test (20 units) and the two marked-wheels proof renders (2 units each): 24 units in that pass. Unit costs for the first 50 tasks weren't recorded.
- One of the 52 is the real upload run through the app's own route (`live_path_check.json`): verdict warn, wheel checks not measured, face and change passed.
- Dollar spend isn't known, because the ledger holds no prices.

## Accessibility

From `accessibility.json`. Axe (WCAG 2.0 and 2.1, A and AA) found 0 violations on the shopper, retailer and how-it-works views and the wheel marker at 1280 and 390 pixels wide, with no sideways scrolling. The first screen's heading, pictures and button fit without scrolling at both widths. The keyboard walk opened and closed the detail dialog, changed the garment with arrow keys, and added, moved, resized and deleted a mark. A touch run placed a mark by tap and moved it by drag. Screens are in `screens/`, and submission screenshots in `screenshots/`.
