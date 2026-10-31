// Marks the wheels through the real control, by mouse and keyboard, and runs the check.
// The marks below were read by eye off the photo; assets/regions.json is never used.
// Usage: node scripts/marked_wheels_proof.mjs http://127.0.0.1:8123 [--upload]
// --upload is a real paid run through the upload path (2 units a garment).
// Without it the sample path is used: saved renders, nothing spent.
import { writeFileSync, mkdirSync, readFileSync } from "node:fs";
import { chromium } from "playwright";

const base = process.argv[2];
const paid = process.argv.includes("--upload");
const MODEL = "m2_studio";
const GARMENTS = ["g1_long_wool_coat", "g4_crop_jacket"];
const OUT = "proof_results/marked_wheels";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: "reduce" })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto(`${base}/#shop`);
await page.waitForSelector("input[name=garment]");
if (paid) await page.setInputFiles("#photo", `assets/models/${MODEL}.png`);
else await page.click("#use-sample");
await page.waitForSelector("#marker:not([hidden])");
await page.waitForFunction(() => document.querySelector("#stage-img").naturalWidth > 0);

const setSlider = (id, v) => page.locator(id).fill(String(v));
const live = () => page.locator("#mark-live").textContent();
const sayings = [];

// Mark 1: mouse. Add it, click the photo where the wheel is, then drag it a little.
await page.click("#add-wheel");
const box = await page.locator("#stage").boundingBox();
await page.mouse.click(box.x + 0.33 * box.width, box.y + 0.7 * box.height);
await page.mouse.move(box.x + 0.33 * box.width, box.y + 0.7 * box.height);
await page.mouse.down();
await page.mouse.move(box.x + 0.352 * box.width, box.y + 0.732 * box.height, { steps: 5 });
await page.mouse.up();
sayings.push(await live());
await setSlider("#s-w", 4.5);
await setSlider("#s-h", 28);
sayings.push(await live());

// Mark 2: keyboard only. Arrow keys move, Shift with arrow keys resizes.
await page.focus("#add-wheel");
await page.keyboard.press("Enter");
for (let i = 0; i < 5; i++) await page.keyboard.press("Shift+ArrowLeft"); // 10% wide to 5%
for (let i = 0; i < 2; i++) await page.keyboard.press("Shift+ArrowDown"); // 30% tall to 28%
await page.keyboard.press("ArrowDown"); // 72% down to 73%
sayings.push(await live());

// Marks 3 and 4: the sliders, as a touch or switch user would.
await page.click("#add-caster");
await setSlider("#s-x", 35.5); await setSlider("#s-y", 87.5); await setSlider("#s-w", 3); await setSlider("#s-h", 10);
sayings.push(await live());
await page.click("#add-caster");
await setSlider("#s-x", 64); await setSlider("#s-y", 87.5); await setSlider("#s-w", 3); await setSlider("#s-h", 10);
sayings.push(await live());

await page.screenshot({ path: `${OUT}/marker_${paid ? "upload" : "sample"}.png`, fullPage: true });
await page.click("#confirm-marks");

const hand = JSON.parse(readFileSync("proof_results/matrix.json", "utf8")).cells;
const runs = [];
for (const g of GARMENTS) {
  await page.locator(`input[value=${g}]`).check({ force: true });
  const [resp] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/api/tryon"), { timeout: 240000 }),
    page.click("#run-live"),
  ]);
  const j = await resp.json();
  await page.waitForSelector("#result .headline, #result .notice");
  if (j.overlay) writeFileSync(`${OUT}/${g}_${paid ? "upload" : "sample"}.jpg`, Buffer.from(j.overlay.split(",")[1], "base64"));
  const h = hand.find((c) => c.model === MODEL && c.garment === g);
  runs.push({
    garment: g, mode: j.mode, saved_render: !!j.saved, error: j.error ?? null, verdict: j.verdict ?? null, wheels_marked: j.wheels_marked ?? 0,
    checks: (j.checks ?? []).map((c) => ({ id: c.id, status: c.status, value: c.value, message: c.message, detail: c.detail })),
    render_returned: !!j.render, verdict_from_eye_marks_in_matrix: h?.verdict ?? null,
    clearance_from_eye_marks_in_matrix: h?.checks.find((c) => c.id === "clearance")?.value ?? null,
  });
}
const marks = await page.evaluate(() => state.marks);
await browser.close();
const report = {
  photo: `assets/models/${MODEL}.png`, path: paid ? "upload, fresh paid render" : "sample button, saved render",
  marks_from: "the marking control in a real browser, read by eye off the photo; no regions.json data",
  marks, live_text_heard: sayings, runs, script_errors: errors,
};
writeFileSync(paid ? "proof_results/marked_wheels_proof.json" : "proof_results/marked_wheels_sample.json", JSON.stringify(report, null, 1));
console.log(JSON.stringify({ sayings, marks, runs: runs.map((r) => [r.garment, r.mode, r.verdict, r.checks.map((c) => `${c.id}=${c.value}/${c.status}`).join(" "), r.verdict_from_eye_marks_in_matrix, r.clearance_from_eye_marks_in_matrix]), errors }, null, 1));
