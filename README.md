# SeatedFit

**Clothes, seen sitting down.** Virtual try-on for people who use wheelchairs, with a check that refuses any picture it can't stand behind.

A long coat looks fine on a standing product photo. On a seated shopper, the same coat covers 59% of a wheel. SeatedFit marks the hem in red, says so in plain words, won't show the picture as a try-on, and puts a cropped jacket that passes beside it.

Try-on images come from YouCam AI Clothes, and skin tone from YouCam's facial colour analysis, so what someone wears and how they look work as one: garments are ordered by measured colour contrast against the shopper's skin. That is a simple contrast calculation, not a style judgement. **All models and garments here are AI-generated and synthetic.** No real person's photo or real brand's product is used.

In the US, 3.6 million people aged 15 and over use a wheelchair or scooter (2010 Survey of Income and Program Participation, in the National Academies' 2017 report [The Promise of Assistive Technology to Enhance Activity and Work Participation](https://www.nationalacademies.org/read/24740/chapter/5)).

## Testing instructions

Live URL: `<LIVE_URL>`. No login, no key and no payment are needed. If it's unavailable, follow [Run it](#run-it): the same saved path runs locally with no key.

**Saved path. This always works and spends nothing.**

1. Open the URL. The first screen shows the same person in two garments: a long coat refused for covering 59% of a wheel, and a cropped jacket passed.
2. Select **Check a garment**. Model B is selected.
3. In step 2, select **Long wool coat**. Step 3 shows a grey evidence picture with the covered wheel in red, and the words "We won't show this as a try-on".
4. Select **See the cropped jacket**. It passes and shows as a normal picture.
5. Above the garments, note the skin tone swatch: garments are listed highest colour contrast first, and each card shows its contrast number and check result.
6. Select **For retailers** for the verdict table, the review list and the approved gallery download. Select any picture for its full check.

**Mark the wheels yourself. Also free.**

1. In step 1, select **No photo to hand? Use this sample as if it were yours**.
2. Select **Add a big wheel**. Click or tap the photo to place the mark, or drag it. By keyboard, arrow keys move it, Shift with arrow keys resizes it, and Delete removes it. The sliders do the same, and the text below them says where the mark is.
3. Add one mark on each big wheel, then select **I've marked all my wheels**.
4. Choose **Long wool coat**, then **Try it on, with wheel checks**. It's refused, using your marks and a saved render. Try **Cropped jacket** for a pass.
5. Move your marks onto the bare wall, select **I've marked all my wheels** again, and run the cropped jacket: it can't pass, and asks you to check your marks.

**Your own photo.** Upload a seated JPG or PNG, mark the wheels, and run a real try-on. This one uses paid YouCam calls and has a daily limit. Past the limit the app says so, and everything above keeps working.

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

- **Shopper:** choose a sample or upload a photo, get a plain-word photo check, mark the wheels on an upload, choose a garment from a list ordered by colour contrast, and see the product photo beside the seated result with the checks underneath.
- **Retailer:** a catalogue × model table with a verdict per picture, a download of approved images with descriptions, and a human review list with reasons.

## Limitations

- It shows how a garment looks in a generated image, not how it truly fits. There's no fabric simulation or body measurement.
- The models are synthetic, and it has not been tested with wheelchair users yet.
- It relies on seated use, which YouCam's documentation does not list as supported.
- **On an upload, wheel and chair checks depend on the shopper's marks.** Automatic wheel finding found 2 of 23 wheels, so it's off. With no marks those checks say "not measured", and the result can't be a full pass. A mark that sits on no wheel-like outline can't earn a pass either. Marks cover wheels only, so footplates and hands aren't compared on an upload.
- Verdicts on marks are sensitive to marking error. With marks up to 2% of the picture off, 154 of 192 reruns kept their verdict, and with 4% off, 96 of 192. Across all of them no refusal became a pass, and one pass became a refusal: see [RESULTS.md](RESULTS.md). This was simulated on the 48 saved renders, not measured with real shoppers.
- Skin tone comes from YouCam on one sample (Model B). The other five samples use a local estimate from the face, and the page says so. An upload gets a YouCam reading while the daily limit lasts, otherwise the local estimate.
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

For live uploads, put `YOURCAM_API_KEY=...` in `.env`. The key stays on the server. `LIVE_DAILY_CAP` sets the daily try-on limit, `LIVE_TONE_DAILY_CAP` the daily skin tone limit, and `LIVE_TASK_CAP` the ledger's total task limit. Past a limit the app says so and carries on from saved results or the local estimate. Uploads are held in memory only, and their metadata is stripped.

```
.venv\Scripts\python.exe -m pytest -q                 # tests, no network
.venv\Scripts\python.exe scripts\run_matrix.py        # re-run the check over saved renders
.venv\Scripts\python.exe scripts\run_planted.py       # re-run planted failures
npm install; npx playwright install chromium
node scripts\a11y.mjs http://127.0.0.1:8000           # accessibility check
node scripts\screenshots.mjs http://127.0.0.1:8000    # submission screenshots
node scripts\marked_wheels_proof.mjs http://127.0.0.1:8000   # marked wheels, saved renders
.venv\Scripts\python.exe scripts\eval_marks.py        # marking error study, about 10 minutes or more
```

## Deploy

One Render web service. [`render.yaml`](render.yaml) holds the config, with this start command:

```
python -m uvicorn seatedfit.app:app --host 0.0.0.0 --port $PORT
```

Set `YOURCAM_API_KEY` as a secret to enable live uploads.

## Accessibility

Full keyboard use, visible focus, real labels, reduced motion, large click targets, and status shown as a word plus a shape, never colour alone. Alt text on each render says what the check found. The wheel marker works by mouse, touch and keyboard, with live text describing each mark. Axe found 0 WCAG A/AA violations on all three views and the marker at desktop and phone width: see [`proof_results/accessibility.json`](proof_results/accessibility.json). Automated checks can't prove real-world usability.

## License

[MIT](LICENSE)
