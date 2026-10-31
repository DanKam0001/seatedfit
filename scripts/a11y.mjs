// Runs axe over every view at desktop and phone width, walks the page by keyboard,
// and saves screenshots. Usage: node scripts/a11y.mjs http://127.0.0.1:8123
import { writeFileSync, mkdirSync } from "node:fs";
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";

const base = process.argv[2];
const OUT = "proof_results/screens";
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const report = { tool: "axe-core via @axe-core/playwright", tags: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"], pages: [] };

for (const [label, viewport] of [["desktop", { width: 1280, height: 900 }], ["phone", { width: 390, height: 844 }]]) {
  const ctx = await browser.newContext({ viewport, reducedMotion: "reduce" });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  for (const view of ["shop", "retail", "how"]) {
    await page.goto(`${base}/#${view}`);
    await page.waitForSelector("#matrix tbody tr", { state: "attached" });
    await page.waitForLoadState("networkidle");
    const axe = await new AxeBuilder({ page }).withTags(report.tags).analyze();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    await page.screenshot({ path: `${OUT}/${view}_${label}.png`, fullPage: view !== "retail" || label === "desktop" });
    report.pages.push({
      view, width: viewport.width, violations: axe.violations.length, passes: axe.passes.length,
      incomplete: axe.incomplete.map((i) => i.id), horizontal_overflow: overflow,
      details: axe.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(" ")).slice(0, 5) })),
    });
  }
  // The first screen must make its point before any scrolling.
  await page.goto(`${base}/#shop`);
  await page.waitForSelector("#hero-pair img");
  await page.waitForLoadState("networkidle");
  const fold = await page.evaluate(() => [...document.querySelectorAll("h1, #hero-pair img, .hero a")]
    .filter((e) => e.offsetParent).every((e) => e.getBoundingClientRect().bottom <= innerHeight));
  report.pages.push({ view: "hero above the fold", width: viewport.width, fits: fold });
  // The marking control, open with two marks and with a result under it.
  await page.click("#use-sample");
  await page.waitForSelector("#marker:not([hidden])");
  await page.waitForFunction(() => document.querySelector("#stage-img").naturalWidth > 0);
  await page.click("#add-wheel");
  await page.click("#add-wheel");
  const marker = await new AxeBuilder({ page }).withTags(report.tags).analyze();
  report.pages.push({
    view: "marking control", width: viewport.width, violations: marker.violations.length, passes: marker.passes.length,
    incomplete: marker.incomplete.map((i) => i.id), horizontal_overflow: await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
    details: marker.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(" ")).slice(0, 5) })),
  });
  report.pages.push({ view: "script errors", width: viewport.width, errors });
  await ctx.close();
}

// Marking with keyboard only, then by touch.
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(`${base}/#shop`);
  await page.waitForSelector("input[name=garment]");
  await page.click("#use-sample");
  await page.waitForSelector("#marker:not([hidden])");
  await page.waitForFunction(() => document.querySelector("#stage-img").naturalWidth > 0);
  const live = () => page.locator("#mark-live").textContent();
  await page.focus("#add-wheel");
  await page.keyboard.press("Enter");
  const added = await live();
  const onMark = await page.evaluate(() => document.activeElement.classList.contains("mark"));
  await page.keyboard.press("ArrowRight");
  const moved = await live();
  await page.keyboard.press("Shift+ArrowRight");
  const resized = await live();
  await page.keyboard.press("Delete");
  const gone = await live();
  report.marking_keyboard = { added, focus_lands_on_the_mark: onMark, moved, resized, after_delete: gone };
  await ctx.close();

  const touch = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  const tp = await touch.newPage();
  await tp.goto(`${base}/#shop`);
  await tp.waitForSelector("input[name=garment]");
  await tp.tap("#use-sample");
  await tp.waitForSelector("#marker:not([hidden])");
  await tp.waitForFunction(() => document.querySelector("#stage-img").naturalWidth > 0);
  await tp.tap("#add-wheel");
  await tp.locator("#stage").scrollIntoViewIfNeeded();
  const box = await tp.locator("#stage").boundingBox();
  await tp.touchscreen.tap(box.x + 0.6 * box.width, box.y + 0.3 * box.height);
  const afterTap = await tp.locator("#mark-live").textContent();
  // A finger drag on the mark, sent as raw touch events.
  const cdp = await touch.newCDPSession(tp);
  const at = (x, y) => [{ x: box.x + x * box.width, y: box.y + y * box.height }];
  await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: at(0.6, 0.3) });
  await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: at(0.5, 0.35) });
  await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: at(0.4, 0.4) });
  await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  report.marking_touch = { after_tap: afterTap, after_drag: await tp.locator("#mark-live").textContent() };
  await touch.close();
}

// Keyboard: everything reachable, the dialog opens with Enter and closes with Escape.
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
await page.goto(`${base}/#retail`);
await page.waitForSelector("#matrix .cell");
await page.locator("#matrix .cell").first().focus();
const focusStyle = await page.evaluate(() => getComputedStyle(document.activeElement).outlineStyle);
await page.keyboard.press("Enter");
const opened = await page.locator("#detail").evaluate((d) => d.open);
await page.screenshot({ path: `${OUT}/detail_desktop.png` });
await page.keyboard.press("Escape");
const closed = !(await page.locator("#detail").evaluate((d) => d.open));
await page.goto(`${base}/#shop`);
await page.waitForSelector("input[name=model]");
await page.locator("input[name=garment]:checked").focus();
await page.keyboard.press("ArrowRight");
const moved = await page.locator("input[name=garment]:checked").getAttribute("value");
const unlabelled = await page.evaluate(() => [...document.images].filter((i) => !i.hasAttribute("alt")).length);
report.keyboard = { dialog_opens_with_enter: opened, dialog_closes_with_escape: closed, arrow_keys_change_garment: moved !== "g1_long_wool_coat", focus_outline_style: focusStyle, images_without_alt: unlabelled };
await browser.close();
writeFileSync("proof_results/accessibility.json", JSON.stringify(report, null, 1));
console.log(JSON.stringify(report.pages.map((p) => [p.view, p.width, p.violations, p.horizontal_overflow, p.details ?? p.errors]), null, 0));
console.log(JSON.stringify([report.keyboard, report.marking_keyboard, report.marking_touch]));
