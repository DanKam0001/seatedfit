# SeatedFit

**Clothes, seen sitting down.** Virtual try-on for people who use wheelchairs, with a check that refuses any picture it can't stand behind.

A long coat looks fine on a standing product photo. On a seated shopper, the same coat covers 59% of a wheel. SeatedFit marks the hem in red, says so in plain words, won't show the picture as a try-on, and puts a cropped jacket that passes beside it.

Try-on images come from YouCam AI Clothes. **All models and garments here are AI-generated and synthetic.** No real person's photo or real brand's product is used.

In the US, 3.6 million people aged 15 and over use a wheelchair or scooter (2010 Survey of Income and Program Participation, in the National Academies' 2017 report [The Promise of Assistive Technology to Enhance Activity and Work Participation](https://www.nationalacademies.org/read/24740/chapter/5)).

## Why a check is needed

YouCam's documentation says photos should have no sitting or crouching, so seated use is outside what it lists as supported. Often it works anyway, but nobody promises the wheelchair survives. SeatedFit measures every render with plain image comparison, with no language model involved:

| Check | Question | How |
|---|---|---|
| Wheel clearance | How much of the worst-covered wheel is under the garment? | New pixels in the garment's colours, inside the marked wheel |
| Wheelchair intact | Is the chair still there? | Similarity, colour damage and wheel outlines against the source photo |
| Face and hands | Is this still the same person? | Similarity on the face and on hands not covered by a sleeve |
| Garment applied | Did anything happen? | Share of the picture that changed |

Each check returns a number, pass, warn or fail, and a region drawn on the picture. A failed render is shown only as grey evidence, never as a try-on.

## Results

From the saved run in [`proof_results/`](proof_results/): 48 renders, 6 synthetic models × 8 garments.

- 32 passed, 3 need a closer look, 13 refused. Every refusal was for wheel clearance.
- All 24 short-garment renders passed. Of the 24 long-garment renders, 13 were refused, 3 warned and 8 passed.
- Planted failures were caught 24 of 24 times in each of five kinds of damage, and 24 of 24 clean renders passed.

Full figures, including what failed, are in [RESULTS.md](RESULTS.md).

## Two views

- **Shopper:** choose a sample or upload a photo, get a plain-word photo check, choose a garment, and see the product photo beside the seated result with the checks underneath.
- **Retailer:** a catalogue × model table with a verdict per picture, a download of approved images with descriptions, and a human review list with reasons.

## Limitations

- It shows how a garment looks in a generated image, not how it truly fits. There's no fabric simulation or body measurement.
- The models are synthetic, and it has not been tested with wheelchair users yet.
- It relies on seated use, which YouCam's documentation does not list as supported.
- **Wheel and chair checks only work on the sample photos**, where wheels are marked by hand. Automatic wheel finding found 2 of 23 wheels, so it's off. On an upload those two checks say "not measured", and the result can never be a full pass.
- Clearance is measured in the picture, so it depends on the pose and angle. The same long coat is refused from some angles and passes from others, where it hangs between the wheels.
- Thresholds were set on these same 48 renders. There's no separate held-out set.

## Run it

Needs Python 3.12.

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m uvicorn seatedfit.app:app --port 8000
```

Then open http://127.0.0.1:8000. It runs from saved renders with no key.

For live uploads, put `YOURCAM_API_KEY=...` in `.env`. The key stays on the server. `LIVE_DAILY_CAP` sets the daily limit, and past it the app says so and shows saved results. Uploads are held in memory only, and their metadata is stripped.

```
.venv\Scripts\python.exe -m pytest -q                 # tests, no network
.venv\Scripts\python.exe scripts\run_matrix.py        # re-run the check over saved renders
.venv\Scripts\python.exe scripts\run_planted.py       # re-run planted failures
npm install; npx playwright install chromium
node scripts\a11y.mjs http://127.0.0.1:8000           # accessibility check
```

## Deploy

One Render web service. [`render.yaml`](render.yaml) holds the config, with this start command:

```
python -m uvicorn seatedfit.app:app --host 0.0.0.0 --port $PORT
```

Set `YOURCAM_API_KEY` as a secret to enable live uploads.

## Accessibility

Full keyboard use, visible focus, real labels, reduced motion, large click targets, and status shown as a word plus a shape, never colour alone. Alt text on each render says what the check found. Axe found 0 WCAG A/AA violations on all three views at desktop and phone width: see [`proof_results/accessibility.json`](proof_results/accessibility.json). Automated checks can't prove real-world usability.

## License

[MIT](LICENSE)
