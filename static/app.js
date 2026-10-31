const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// Status is always a word plus a shape, never colour alone.
const SHAPES = {
  pass: '<circle cx="9" cy="9" r="8"/><path d="M5 9.5l3 3 5-6" fill="none" stroke="#fff" stroke-width="2"/>',
  warn: '<path d="M9 1l8.5 15h-17z"/><path d="M9 7v4M9 13v1.5" stroke="#fff" stroke-width="2"/>',
  fail: '<rect x="1" y="1" width="16" height="16" rx="2"/><path d="M5 5l8 8M13 5l-8 8" stroke="#fff" stroke-width="2"/>',
  other: '<circle cx="9" cy="9" r="7" fill="none" stroke="currentColor" stroke-width="2"/>',
};
const WORDS = { pass: "Passed", warn: "Look closer", fail: "Refused", not_measured: "Not measured", no_render: "No picture" };
const badge = (s, text) => `<span class="badge s-${s}"><svg viewBox="0 0 18 18" fill="currentColor" aria-hidden="true">${SHAPES[s] || SHAPES.other}</svg>${esc(text || WORDS[s])}</span>`;

const NAMES = { m1_studio: "Model A", m2_studio: "Model B", m3_home: "Model C", m4_home: "Model D", m5_outdoor: "Model E", m6_side: "Model F" };
const state = { catalogue: null, matrix: null, model: "m2_studio", garment: "g1_long_wool_coat", file: null, sample: null, marks: [], selected: -1, confirmed: false, tone: null };

const cell = (m, g) => state.matrix.cells.find((c) => c.model === m && c.garment === g);
const garment = (g) => state.catalogue.garments.find((x) => x.id === g);
const modelDesc = (m) => state.catalogue.models.find((x) => x.id === m).description;

function numberLine(c) {
  if (c.value == null) return "";
  if (c.id === "clearance") return `${(c.value * 100).toFixed(1)}% of the worst-covered wheel`;
  if (c.id === "change") return `${(c.value * 100).toFixed(1)}% of the picture changed`;
  return `${c.value} similarity, where 1 is identical`;
}

function checksList(checks) {
  return `<ul class="checks">${checks.map((c) => `<li><h3>${esc(c.name)}</h3>${badge(c.status)}<p>${esc(c.message)}</p><p class="num-line">${esc(numberLine(c))}</p></li>`).join("")}</ul>`;
}

function headline(c) {
  const clr = c.checks.find((x) => x.id === "clearance");
  const pct = clr && clr.value != null ? Math.round(clr.value * 100) : null;
  if (c.verdict === "pass") return { big: "Clear of the wheels.", sub: "All four checks passed. This picture can be trusted as an image, not as a measure of fit." };
  const worst = c.checks.find((x) => x.status === c.verdict && x.id !== "clearance");
  if (clr && clr.status === c.verdict && pct) {
    return { big: `This garment covers ${pct}% of a wheel.`, sub: c.verdict === "fail" ? "We won't show this as a try-on. The grey picture is our evidence, with the covered part in red." : "It's close. Look at the marked wheel before you decide." };
  }
  return { big: c.verdict === "fail" ? "We won't show this one." : "Look closer before you trust this.", sub: worst ? worst.message : clr ? clr.message : "" };
}

function resultHtml(c, g, productSrc, imageSrc, alt) {
  const h = headline(c);
  return `<div class="headline s-${c.verdict}">${badge(c.verdict)}<p class="big">${esc(h.big)}</p><p>${esc(h.sub)}</p></div>
  <div class="compare">
    <figure class="frame"><img src="${productSrc}" alt="Product photo of the ${esc(g.name.toLowerCase())}, shown flat as a shop would show it." width="640" height="640"><figcaption><strong>Product photo</strong>How the shop shows it.</figcaption></figure>
    <figure class="frame"><img src="${imageSrc}" alt="${esc(alt)}" width="720" height="720"><figcaption><strong>${c.verdict === "fail" ? "Refused: evidence, not a try-on" : "Seated, checked"}</strong>Wheels are outlined. Red marks garment over a wheel.</figcaption></figure>
  </div>${checksList(c.checks)}`;
}

function renderSaved() {
  const c = cell(state.model, state.garment);
  const g = garment(state.garment);
  const box = $("#result");
  if (!c) { box.innerHTML = ""; return; }
  if (c.verdict === "no_render") {
    box.innerHTML = `<div class="headline s-no_render">${badge("no_render")}<p class="big">There's no picture for this pair.</p><p>The try-on service refused it (${esc(c.api_error)}).</p></div>`;
    return;
  }
  let html = resultHtml(c, g, `/media/garments/${g.id}.jpg`, `/media/overlays/${c.web}`, c.alt);
  if (c.verdict !== "pass") {
    const alt = state.catalogue.garments.map((x) => cell(state.model, x.id)).find((x) => x && x.verdict === "pass");
    if (alt) {
      const ag = garment(alt.garment);
      html += `<div class="instead"><h3>Passed on the same person</h3><div class="instead-row"><img src="/media/overlays/${alt.web}" alt="${esc(alt.alt)}" width="720" height="720"><div>${badge("pass")}<p>The ${esc(ag.name.toLowerCase())} clears the wheels and keeps the chair intact.</p><button type="button" class="link-btn" data-switch="${ag.id}">See the ${esc(ag.name.toLowerCase())}</button></div></div></div>`;
    }
  }
  box.innerHTML = html;
  const sw = box.querySelector("[data-switch]");
  if (sw) sw.addEventListener("click", () => {
    state.garment = sw.dataset.switch;
    document.querySelector(`input[name=garment][value=${state.garment}]`).checked = true;
    renderSaved();
    $("#result-step h2").scrollIntoView();
  });
}

function buildHero() {
  const pair = [["g1_long_wool_coat"], ["g4_crop_jacket"]].map(([g]) => cell(state.model, g)).filter((c) => c && c.web);
  $("#hero-pair").innerHTML = pair.map((c) => {
    const g = garment(c.garment);
    const clr = c.checks.find((x) => x.id === "clearance");
    const line = c.verdict === "fail" ? `Covers ${Math.round(clr.value * 100)}% of a wheel` : `Covers ${Math.round(clr.value * 100)}% of a wheel. Clear.`;
    return `<figure class="hero-fig"><img src="/media/overlays/${c.web}" alt="${esc(c.alt)}" width="720" height="720"><figcaption>${badge(c.verdict)}<strong>${esc(g.name)}</strong><span>${esc(line)}</span></figcaption></figure>`;
  }).join("");
}

function toneCopy(t) {
  if (t.source === "youcam") return "Skin tone measured by YouCam from the face.";
  return "Skin tone estimated from this photo's pixels, because each YouCam reading costs paid units.";
}

function orderGarments() {
  const t = state.tone;
  const rail = $("#garment-rail");
  rail.querySelectorAll(".contrast").forEach((x) => x.remove());
  if (!t) return;
  for (const r of t.garments) {
    const label = rail.querySelector(`input[value=${r.garment}]`).closest(".pick");
    const c = !state.file || state.sample ? cell(state.file ? state.sample : state.model, r.garment) : null;
    const check = c ? badge(c.verdict) : "";
    label.insertAdjacentHTML("beforeend", `<span class="contrast"><i class="swatch" style="background:${esc(r.colour)}" aria-hidden="true"></i>Contrast ${r.contrast.toFixed(1)}${check}</span>`);
    rail.appendChild(label);
  }
  $("#tone").innerHTML = `<i class="swatch big" style="background:${esc(t.skin)}" aria-hidden="true"></i><p><strong>Highest colour contrast first.</strong> ${esc(t.message || toneCopy(t))} This is a simple contrast calculation (CIEDE2000), not a style judgement. Check results come from the wheels, not the colour.</p>`;
}

async function loadTone() {
  state.tone = await fetch(`/api/tone/${state.sample || state.model}`).then((r) => r.json());
  orderGarments();
}

function offerTone() {
  state.tone = null;
  orderGarments();
  $("#tone").innerHTML = '<p>Want the garments ordered by colour contrast against your skin tone? Only a crop of your face is sent to YouCam to measure it.</p><button type="button" class="link-btn" id="measure-tone">Measure my skin tone</button>';
  $("#measure-tone").addEventListener("click", async () => {
    $("#tone").innerHTML = "<p>Measuring.</p>";
    const fd = new FormData();
    fd.append("photo", state.file);
    const r = await fetch("/api/tone", { method: "POST", body: fd });
    const j = await r.json();
    if (!r.ok) { $("#tone").innerHTML = `<p>${esc(j.detail)}</p>`; return; }
    state.tone = j;
    orderGarments();
  });
}

// Wheel marks. Each is fractions of the photo: centre x, y, full width w, height h.
const pct = (v) => Math.round(v * 100);
const markName = (m, i) => `${m.kind === "wheel" ? "Big wheel" : "Small wheel"} ${i + 1}`;
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const describe = (m, i) => `${markName(m, i)}: ${pct(m.x)}% across, ${pct(m.y)}% down, ${pct(m.w)}% wide, ${pct(m.h)}% tall.`;

function drawMarks(focus) {
  const box = $("#marks");
  box.innerHTML = state.marks.map((m, i) => `<button type="button" class="mark${i === state.selected ? " on" : ""}" data-i="${i}" aria-describedby="marker-help" aria-label="${esc(describe(m, i))}" style="left:${(m.x - m.w / 2) * 100}%;top:${(m.y - m.h / 2) * 100}%;width:${m.w * 100}%;height:${m.h * 100}%"><span>${i + 1}</span></button>`).join("");
  const m = state.marks[state.selected];
  $("#mark-sliders").hidden = !m;
  if (m) {
    $("#s-x").value = m.x * 100; $("#s-y").value = m.y * 100; $("#s-w").value = m.w * 100; $("#s-h").value = m.h * 100;
  }
  if (focus) box.querySelector(".mark.on")?.focus();
  const canConfirm = state.marks.some((x) => x.kind === "wheel");
  $("#confirm-marks").disabled = !canConfirm;
  $("#confirm-marks").textContent = state.confirmed ? "Marks saved" : "I've marked all my wheels";
  $("#run-live").textContent = state.confirmed ? "Try it on, with wheel checks" : "Try it on without wheel checks";
}

function say(text) { $("#mark-live").textContent = text; }

function changed(focus = true) {
  state.confirmed = false;
  drawMarks(focus);
  const m = state.marks[state.selected];
  say(m ? describe(m, state.selected) : `${state.marks.length} ${state.marks.length === 1 ? "mark" : "marks"} placed.`);
}

function addMark(kind) {
  if (state.marks.length >= 6) { say("Six marks is the most we can use."); return; }
  const side = state.marks.length % 2 ? 0.65 : 0.35;
  state.marks.push(kind === "wheel" ? { kind, x: side, y: 0.72, w: 0.1, h: 0.3 } : { kind, x: side, y: 0.88, w: 0.05, h: 0.1 });
  state.selected = state.marks.length - 1;
  changed();
}

function removeMark() {
  state.marks.splice(state.selected, 1);
  state.selected = state.marks.length - 1;
  changed(false);
  (state.selected >= 0 ? $(".mark.on") : $("#add-wheel")).focus();
}

function moveTo(e) {
  const r = $("#stage").getBoundingClientRect();
  const m = state.marks[state.selected];
  m.x = clamp((e.clientX - r.left) / r.width, 0, 1);
  m.y = clamp((e.clientY - r.top) / r.height, 0, 1);
}

function setupMarker() {
  const stage = $("#stage");
  stage.addEventListener("pointerdown", (e) => {
    const hit = e.target.closest(".mark");
    if (hit) {
      state.selected = +hit.dataset.i;
      stage.setPointerCapture(e.pointerId);
      stage.dataset.drag = "1";
      changed();
    } else if (state.selected >= 0) {
      moveTo(e);
      changed();
    }
  });
  stage.addEventListener("pointermove", (e) => {
    if (stage.dataset.drag) { moveTo(e); changed(false); }
  });
  const stop = () => { delete stage.dataset.drag; $(".mark.on")?.focus(); };
  stage.addEventListener("pointerup", stop);
  stage.addEventListener("pointercancel", stop);
  $("#marks").addEventListener("focusin", (e) => {
    const hit = e.target.closest(".mark");
    if (hit && +hit.dataset.i !== state.selected) { state.selected = +hit.dataset.i; drawMarks(true); say(describe(state.marks[state.selected], state.selected)); }
  });
  $("#marks").addEventListener("keydown", (e) => {
    const m = state.marks[state.selected];
    if (!m) return;
    if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); removeMark(); return; }
    const d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
    if (!d) return;
    e.preventDefault();
    const step = 0.01;
    if (e.shiftKey) {
      m.w = clamp(m.w + d[0] * step, 0.02, 0.8);
      m.h = clamp(m.h - d[1] * step, 0.02, 0.8);
    } else {
      m.x = clamp(m.x + d[0] * step, 0, 1);
      m.y = clamp(m.y + d[1] * step, 0, 1);
    }
    changed();
  });
  for (const k of ["x", "y", "w", "h"]) {
    $(`#s-${k}`).addEventListener("input", (e) => { state.marks[state.selected][k] = e.target.value / 100; changed(false); });
  }
  $("#add-wheel").addEventListener("click", () => addMark("wheel"));
  $("#add-caster").addEventListener("click", () => addMark("caster"));
  $("#remove-mark").addEventListener("click", removeMark);
  $("#confirm-marks").addEventListener("click", () => {
    state.confirmed = true;
    drawMarks(false);
    say(`${state.marks.length} ${state.marks.length === 1 ? "mark" : "marks"} saved for the wheel checks.`);
  });
}

function buildRails() {
  $("#model-rail").insertAdjacentHTML("beforeend", state.catalogue.models.map((m) =>
    `<label class="pick"><input type="radio" name="model" value="${m.id}" ${m.id === state.model ? "checked" : ""}><img src="/media/models/${m.id}.jpg" alt="${esc(m.description)}. AI-generated." width="640" height="640" loading="lazy"><span>${esc(NAMES[m.id])}</span></label>`).join(""));
  $("#garment-rail").insertAdjacentHTML("beforeend", state.catalogue.garments.map((g) =>
    `<label class="pick"><input type="radio" name="garment" value="${g.id}" ${g.id === state.garment ? "checked" : ""}><img src="/media/garments/${g.id}.jpg" alt="${esc(g.name)}, product photo. AI-generated." width="640" height="640" loading="lazy"><span>${esc(g.name)}</span></label>`).join(""));
  $("#model-rail").addEventListener("change", (e) => { state.model = e.target.value; clearPhoto(); renderSaved(); loadTone(); });
  $("#garment-rail").addEventListener("change", (e) => { state.garment = e.target.value; if (!state.file) renderSaved(); });
}

function clearPhoto() {
  state.file = null;
  state.sample = null;
  state.marks = [];
  state.selected = -1;
  state.confirmed = false;
  if ($("#stage-img").src.startsWith("blob:")) URL.revokeObjectURL($("#stage-img").src);
  $("#stage-img").removeAttribute("src");
  $("#marks").innerHTML = "";
  say("No wheels marked yet.");
  $("#marker").hidden = true;
  $("#photo").value = "";
  $("#photo-report").innerHTML = "";
  $("#clear-photo").hidden = true;
  $("#run-live").hidden = true;
}

async function checkPhoto(file) {
  state.file = file;
  $("#clear-photo").hidden = false;
  const box = $("#photo-report");
  box.innerHTML = "<p>Checking your photo.</p>";
  const fd = new FormData();
  fd.append("photo", file);
  const r = await fetch("/api/photo-check", { method: "POST", body: fd });
  const j = await r.json();
  if (!r.ok) { box.innerHTML = `<p class="notice">${esc(j.detail)}</p>`; return; }
  box.innerHTML = `<ul class="list-check">${j.items.map((i) => `<li>${badge(i.status, i.label)}<br>${esc(i.message)}</li>`).join("")}</ul>`;
  $("#run-live").hidden = !j.ok;
  $("#marker").hidden = !j.ok;
  $("#result").innerHTML = "";
  if (j.ok) {
    $("#stage-img").src = URL.createObjectURL(file);
    drawMarks(false);
    if (state.sample) await loadTone(); else offerTone();
  }
}

async function onPhoto() {
  const file = $("#photo").files[0];
  if (!file) return clearPhoto();
  state.sample = null;
  await checkPhoto(file);
}

async function useSample() {
  const m = state.model;
  const blob = await fetch(`/api/sample-photo/${m}`).then((r) => r.blob());
  clearPhoto();
  state.sample = m;
  await checkPhoto(new File([blob], `${m}.png`, { type: "image/png" }));
}

async function runLive() {
  const box = $("#result");
  const btn = $("#run-live");
  btn.disabled = true;
  box.innerHTML = "<p>Making your try-on. This can take a minute.</p>";
  $("#result-step h2").scrollIntoView();
  const fd = new FormData();
  if (state.sample) fd.append("sample", state.sample); else fd.append("photo", state.file);
  fd.append("garment", state.garment);
  if (state.confirmed) fd.append("wheels", JSON.stringify(state.marks));
  try {
    const r = await fetch("/api/tryon", { method: "POST", body: fd });
    const j = await r.json();
    if (j.mode === "fallback") {
      clearPhoto();
      box.innerHTML = "";
      renderSaved();
      loadTone();
      box.insertAdjacentHTML("afterbegin", `<p class="notice">${esc(j.message)}</p>`);
    } else if (j.mode === "live") {
      const g = garment(state.garment);
      box.innerHTML = resultHtml(j, g, `/media/garments/${g.id}.jpg`, j.overlay, j.alt);
      if (j.saved) box.insertAdjacentHTML("afterbegin", '<p class="notice">This is a saved try-on of the sample, so nothing was spent. The check just ran on your marks.</p>');
    } else {
      box.innerHTML = `<p class="notice">${esc(j.message || j.detail || "Your photo did not pass the check above.")}</p>`;
    }
  } catch {
    box.innerHTML = '<p class="notice">Something went wrong reaching the server. Please try again.</p>';
  }
  btn.disabled = false;
}

function reasons(c) {
  if (c.verdict === "no_render") return `Try-on service returned ${c.api_error}.`;
  return c.checks.filter((x) => x.status !== "pass").map((x) => `${x.name}: ${x.message}`).join(" ");
}

function buildRetail() {
  const { counts, cells } = state.matrix;
  const rows = [["Approved", counts.pass], ["Look closer", counts.warn], ["Refused", counts.fail], ["No picture", counts.no_render], ["Pictures run", state.matrix.cells_total]];
  $("#counts").innerHTML = rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
  const gs = state.catalogue.garments, ms = state.catalogue.models;
  $("#matrix").innerHTML = `<caption class="sr">Check result for each garment on each seated model</caption><thead><tr><td></td>${ms.map((m) => `<th scope="col">${esc(NAMES[m.id])}</th>`).join("")}</tr></thead><tbody>${gs.map((g) => `<tr><th scope="row"><img src="/media/garments/${g.id}.jpg" alt="" width="64" height="64" loading="lazy">${esc(g.name)}</th>${ms.map((m) => {
    const c = cell(m.id, g.id);
    if (!c) return "<td></td>";
    if (!c.web) return `<td>${badge("no_render")}</td>`;
    return `<td><button type="button" class="cell" data-m="${m.id}" data-g="${g.id}"><img src="/media/overlays/${c.web}" alt="${esc(c.alt)}" width="720" height="720" loading="lazy">${badge(c.verdict)}</button></td>`;
  }).join("")}</tr>`).join("")}</tbody>`;
  $("#matrix").addEventListener("click", (e) => {
    const b = e.target.closest(".cell");
    if (b) openDetail(b.dataset.m, b.dataset.g);
  });
  const order = { fail: 0, no_render: 1, warn: 2 };
  const review = cells.filter((c) => c.verdict !== "pass").sort((a, b) => order[a.verdict] - order[b.verdict]);
  $("#review").innerHTML = review.map((c) => `<li>${c.web ? `<img src="/media/overlays/${c.web}" alt="${esc(c.alt)}" width="720" height="720" loading="lazy">` : "<span></span>"}<div>${badge(c.verdict)}<h3>${esc(garment(c.garment).name)} on ${esc(NAMES[c.model])}</h3><p>${esc(reasons(c))}</p></div></li>`).join("");
}

function openDetail(m, g) {
  const c = cell(m, g);
  const gm = garment(g);
  $("#detail-body").innerHTML = `<h2 id="detail-title">${esc(gm.name)} on ${esc(NAMES[m])}</h2><p class="note">${esc(modelDesc(m))}. AI-generated.</p>${resultHtml(c, gm, `/media/garments/${g}.jpg`, `/media/overlays/${c.web}`, c.alt)}`;
  $("#detail").showModal();
}

function route() {
  const v = (location.hash || "#shop").slice(1);
  const view = ["shop", "retail", "how"].includes(v) ? v : "shop";
  document.querySelectorAll(".view").forEach((s) => { s.hidden = s.id !== `view-${view}`; });
  document.querySelectorAll("[data-view]").forEach((a) => {
    if (a.dataset.view === view) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  document.title = { shop: "SeatedFit: try-on for people who sit", retail: "SeatedFit for retailers", how: "How SeatedFit checks a try-on" }[view];
}

async function start() {
  [state.catalogue, state.matrix] = await Promise.all([fetch("/api/catalogue").then((r) => r.json()), fetch("/api/matrix").then((r) => r.json())]);
  buildRails();
  buildHero();
  setupMarker();
  renderSaved();
  buildRetail();
  loadTone();
  $("#photo").addEventListener("change", onPhoto);
  $("#use-sample").addEventListener("click", useSample);
  $("#clear-photo").addEventListener("click", () => { clearPhoto(); renderSaved(); loadTone(); });
  $("#run-live").addEventListener("click", runLive);
  addEventListener("hashchange", () => { route(); $("#main").focus({ preventScroll: true }); });
  route();
}
start();
