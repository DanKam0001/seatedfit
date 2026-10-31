// Saves each main screen for the submission form. Spends nothing: saved renders only.
// Usage: node scripts/screenshots.mjs http://127.0.0.1:8123
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const base = process.argv[2];
const OUT = "proof_results/screenshots";
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const shot = (page, name, opts = {}) => page.screenshot({ path: `${OUT}/${name}.png`, ...opts });

async function open(viewport, hash) {
  const page = await (await browser.newContext({ viewport, reducedMotion: "reduce" })).newPage();
  await page.goto(`${base}/${hash}`);
  await page.waitForLoadState("networkidle");
  return page;
}

const desktop = { width: 1280, height: 900 };
await shot(await open(desktop, "#shop"), "01_first_screen_desktop");
await shot(await open({ width: 390, height: 844 }, "#shop"), "01_first_screen_phone");

const page = await open(desktop, "#shop");
const pick = async (g) => {
  await page.locator(`input[value=${g}]`).check({ force: true });
  await page.waitForSelector("#result .headline");
  await page.locator("#result-step").scrollIntoViewIfNeeded();
};
await pick("g1_long_wool_coat");
await page.locator("#result-step").screenshot({ path: `${OUT}/02_refused_result.png` });
await pick("g4_crop_jacket");
await page.locator("#result-step").screenshot({ path: `${OUT}/03_passed_result.png` });
await page.locator("#tone").scrollIntoViewIfNeeded();
await page.locator("#tone").locator("..").screenshot({ path: `${OUT}/04_contrast_order.png` });

await page.click("#use-sample");
await page.waitForSelector("#marker:not([hidden])");
await page.waitForFunction(() => document.querySelector("#stage-img").naturalWidth > 0);
const set = (id, v) => page.locator(id).fill(String(v));
for (const [x, y, w, h] of [[35.5, 73, 4.5, 28], [65, 73, 5, 28]]) {
  await page.click("#add-wheel");
  await set("#s-x", x); await set("#s-y", y); await set("#s-w", w); await set("#s-h", h);
}
await page.locator("#marker").screenshot({ path: `${OUT}/05_mark_your_wheels.png` });
await page.click("#confirm-marks");
await page.locator("input[value=g1_long_wool_coat]").check({ force: true });
await Promise.all([page.waitForResponse((r) => r.url().endsWith("/api/tryon")), page.click("#run-live")]);
await page.waitForSelector("#result .headline");
await page.locator("#result-step").screenshot({ path: `${OUT}/06_marked_wheels_result.png` });

const retail = await open(desktop, "#retail");
await retail.waitForSelector("#matrix .cell");
await shot(retail, "07_retailer", { fullPage: true });
await retail.locator("#matrix .cell").first().focus();
await retail.keyboard.press("Enter");
await retail.waitForTimeout(300);
await shot(retail, "08_render_detail");
await shot(await open(desktop, "#how"), "09_how_it_works", { fullPage: true });
await browser.close();
