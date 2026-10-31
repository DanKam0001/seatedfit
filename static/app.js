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
const state = { catalogue: null, matrix: null, model: "m2_studio", garment: "g1_long_wool_coat", file: null };

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
  if (c.verdict === "pass") return { big: "Clear of the wheels.", sub: "All four checks passed. This picture can be trusted as an image." };
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

function buildRails() {
  $("#model-rail").insertAdjacentHTML("beforeend", state.catalogue.models.map((m) =>
    `<label class="pick"><input type="radio" name="model" value="${m.id}" ${m.id === state.model ? "checked" : ""}><img src="/media/models/${m.id}.jpg" alt="${esc(m.description)}. AI-generated." width="640" height="640" loading="lazy"><span>${esc(NAMES[m.id])}</span></label>`).join(""));
  $("#garment-rail").insertAdjacentHTML("beforeend", state.catalogue.garments.map((g) =>
    `<label class="pick"><input type="radio" name="garment" value="${g.id}" ${g.id === state.garment ? "checked" : ""}><img src="/media/garments/${g.id}.jpg" alt="${esc(g.name)}, product photo. AI-generated." width="640" height="640" loading="lazy"><span>${esc(g.name)}</span></label>`).join(""));
  $("#model-rail").addEventListener("change", (e) => { state.model = e.target.value; clearPhoto(); renderSaved(); });
  $("#garment-rail").addEventListener("change", (e) => { state.garment = e.target.value; if (!state.file) renderSaved(); });
}

function clearPhoto() {
  state.file = null;
  $("#photo").value = "";
  $("#photo-report").innerHTML = "";
  $("#clear-photo").hidden = true;
  $("#run-live").hidden = true;
}

async function onPhoto() {
  const file = $("#photo").files[0];
  if (!file) return clearPhoto();
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
  $("#result").innerHTML = "";
}

async function runLive() {
  const box = $("#result");
  const btn = $("#run-live");
  btn.disabled = true;
  box.innerHTML = "<p>Making your try-on. This can take a minute.</p>";
  $("#result-step h2").scrollIntoView();
  const fd = new FormData();
  fd.append("photo", state.file);
  fd.append("garment", state.garment);
  try {
    const r = await fetch("/api/tryon", { method: "POST", body: fd });
    const j = await r.json();
    if (j.mode === "fallback") {
      clearPhoto();
      box.innerHTML = "";
      renderSaved();
      box.insertAdjacentHTML("afterbegin", `<p class="notice">${esc(j.message)}</p>`);
    } else if (j.mode === "live") {
      const g = garment(state.garment);
      box.innerHTML = resultHtml(j, g, `/media/garments/${g.id}.jpg`, j.overlay, j.alt);
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
  renderSaved();
  buildRetail();
  $("#photo").addEventListener("change", onPhoto);
  $("#clear-photo").addEventListener("click", () => { clearPhoto(); renderSaved(); });
  $("#run-live").addEventListener("click", runLive);
  addEventListener("hashchange", () => { route(); $("#main").focus({ preventScroll: true }); });
  route();
}
start();
