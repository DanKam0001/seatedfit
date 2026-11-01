# Evidence notes

Facts in the submission that come from outside the saved matrix run, with where each one can be checked.

## Wheelchair users
In the US, 3.6 million people aged 15 and over use a wheelchair or scooter. Source: 2010 Survey of Income and Program
Participation, in the National Academies' 2017 report "The Promise of Assistive Technology to Enhance Activity and Work
Participation": https://www.nationalacademies.org/read/24740/chapter/5

## YouCam's documented photo conditions
`docs/ai_clothes.md`, target user image: "The body must be facing forward in a standing position (no sitting or crouching)."
So seated use is outside the documented conditions.

## First test on seated photos
`first_test.json`, copied from `assets/probe/seated_test.json`: 6 of 6 tasks succeeded, on 3 seated models and 2 garment
categories (full_body and upper_body). The models were synthetic. One sat on an ordinary chair and two in wheelchairs.

## Render size
All 48 renders in `renders/` have the same pixel dimensions as their source photo in `assets/models/`: 48 same, 0 different.
Measured by opening each pair. This is a size check. It does not prove every pixel lines up.

## Accessibility in the code
- Reduced motion: `prefers-reduced-motion` rule in `static/style.css`.
- Click targets: navigation and slider rows have `min-height: 44px` in `static/style.css`.
- Status as a word plus a shape: each verdict shows a word with an icon, in the screenshots in `screenshots/`.
- Axe found 0 WCAG A/AA violations: `accessibility.json`. Automated checks can't prove real-world usability.

## API and views in the code
- AI Clothes endpoint `cloth-v4`: `TASK_PATH` in `seatedfit/youcam.py`, with every call logged in `youcam_calls.jsonl`.
- Retailer view: `screenshots/07_retailer.png` shows the garment by model table. Approved images download from `/api/gallery.zip`
  in `seatedfit/app.py`, and the review list with reasons is built from `matrix.json`.
- Review list: `static/app.js` lists every cell whose verdict is not pass, with its reasons, in the `#review` list.
- Garment order: `static/app.js` shows "Highest colour contrast first", with a contrast number on each garment.
- Visible focus: `:focus-visible` rule in `static/style.css`. Real labels: `<label>` elements in `static/index.html`.

## Refused renders and the retailer download
- Refused renders: `app.py` withholds the render when the verdict is fail and sends only the overlay. `screenshots/02_refused_result.png`
  shows that overlay: a grey picture with the covered part of the wheel in red.
- Retailer view: `gallery()` at `/api/gallery.zip` in `app.py` builds the approved images download, shown in `screenshots/07_retailer.png`.
  The human review list with reasons is the `#review` list in `static/app.js`.
