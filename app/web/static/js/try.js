/* Playground for the Tajik OCR API: upload -> call the same endpoints a program would -> friendly result. */
(function () {
  const { t, store } = window.Site;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const MAX_MB = 15;
  const IMG_EXT = /\.(jpe?g|png|webp|bmp|tiff?)$/i;
  const MODES = {
    hr: { path: "/hr/passport", slots: ["front", "back"], need: "both" },
    passport: { path: "/passport", slots: ["front", "back"], need: "any" },
    ocr: { path: "/ocr", slots: ["file"], need: "all" },
  };
  const SLOT = {
    front: { title: "up.front", hint: "up.front.hint", file: "front.jpg" },
    back: { title: "up.back", hint: "up.back.hint", file: "back.jpg" },
    file: { title: "up.image", hint: "up.image.hint", file: "image.png" },
  };
  const NOT_ON_CARD = ["phone", "phone_2", "email"];
  // Fictional specimens ("НАМУНА / SPECIMEN"), see scripts/make_specimens.py
  const SAMPLES = { front: "/static/demo/card_front.webp", back: "/static/demo/card_back.webp", file: "/static/demo/text.webp" };
  const PP_ALIAS = { sex: "gender", birth_date: "date_of_birth", document_number: "passport_id", tax_id: "inn" };

  const state = {
    mode: "hr",
    files: {}, // slot -> File
    urls: {}, // slot -> object URL
    result: null, // { mode, data, files }
    error: null,
    edits: {},
    busy: false,
    codeLang: store.get("tocr.code") || "curl",
  };

  /* ---------------- options ---------------- */
  function opts() {
    const f = $("#form");
    return {
      lang: f.lang.value,
      engine: f.engine.value,
      flatten: f.flatten.checked,
      deskew: f.deskew.checked,
      min_score: Number(f.min_score.value),
    };
  }

  function requestUrl(mode = state.mode, o = opts(), origin = location.origin) {
    const q = new URLSearchParams();
    if (mode === "hr") q.set("lang", o.lang);
    if (mode === "ocr") {
      q.set("engine", o.engine);
      q.set("flatten", o.flatten);
      q.set("deskew", o.deskew);
      if (o.min_score > 0) q.set("min_score", o.min_score);
    }
    const qs = q.toString();
    return origin + MODES[mode].path + (qs ? "?" + qs : "");
  }

  /* ---------------- drop zones ---------------- */
  function setFile(slot, file, fromSample = false) {
    if (!fromSample) showDemoBanner(false);
    if (state.urls[slot]) URL.revokeObjectURL(state.urls[slot]);
    delete state.urls[slot];
    if (!file) { delete state.files[slot]; renderDrops(); return; }
    const isImg = (file.type || "").startsWith("image/") || IMG_EXT.test(file.name);
    if (!isImg) return flash(`${t("up.notImage")}: ${file.name}`);
    if (file.size > MAX_MB * 1024 * 1024) return flash(`${t("up.tooBig")}: ${file.name}`);
    state.files[slot] = file;
    state.urls[slot] = URL.createObjectURL(file);
    flash("");
    renderDrops();
  }

  function renderDrops() {
    const box = $("#drops");
    const slots = MODES[state.mode].slots;
    box.classList.toggle("single", slots.length === 1);
    box.innerHTML = "";
    for (const slot of slots) {
      const s = SLOT[slot];
      const file = state.files[slot];
      const el = document.createElement("label");
      el.className = "drop" + (file ? " has" : "");
      if (file) {
        el.innerHTML = `<span class="tag">${esc(t(s.title))}</span>
          <img alt="" src="${state.urls[slot]}" onerror="this.style.display='none'">
          <span class="meta"><span>${esc(file.name)} · ${(file.size / 1024 / 1024).toFixed(1)} MB</span>
          <button type="button" data-remove>${esc(t("up.remove"))}</button></span>`;
      } else {
        el.innerHTML = `<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="color:var(--muted)">
            <path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v2.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V16"/></svg>
          <span class="t">${esc(t(s.title))}</span><span class="h">${esc(t(s.hint))}</span>
          <span class="cta">${esc(t("up.drop"))}</span>`;
      }
      const input = document.createElement("input");
      input.type = "file";
      input.accept = "image/*,.tif,.tiff,.bmp,.webp";
      input.setAttribute("aria-label", t(s.title));
      if (file) input.tabIndex = -1;
      input.addEventListener("change", () => input.files[0] && setFile(slot, input.files[0]));
      el.prepend(input);
      if (file) input.style.display = "none";
      el.addEventListener("dragover", (e) => { e.preventDefault(); el.classList.add("over"); });
      el.addEventListener("dragleave", () => el.classList.remove("over"));
      el.addEventListener("drop", (e) => {
        e.preventDefault(); el.classList.remove("over");
        const files = [...e.dataTransfer.files];
        if (!files.length) return;
        setFile(slot, files[0]);
        // two files dropped on the first zone: fill the other side too
        if (files[1]) { const other = slots.find((x) => x !== slot && !state.files[x]); if (other) setFile(other, files[1]); }
      });
      const rm = el.querySelector("[data-remove]");
      if (rm) rm.addEventListener("click", (e) => { e.preventDefault(); setFile(slot, null); });
      box.append(el);
    }
    const hint = $("#drop-hint");
    hint.textContent = state.mode === "hr" ? t("up.swap") : state.mode === "passport" ? t("up.oneSide") : "";
    hint.style.display = hint.textContent ? "" : "none";
    const sb = $("#sample-btn");
    sb.textContent = t(state.mode === "ocr" ? "up.useSampleText" : "up.useSample");
    sb.hidden = slots.every((s) => state.files[s]);
    renderCode();
  }

  // paste an image from the clipboard into the first empty slot
  document.addEventListener("paste", (e) => {
    const f = [...(e.clipboardData?.files || [])].find((x) => (x.type || "").startsWith("image/"));
    if (!f) return;
    const slot = MODES[state.mode].slots.find((s) => !state.files[s]) || MODES[state.mode].slots[0];
    setFile(slot, f);
  });

  function showDemoBanner(on) { $("#demo-banner").hidden = !on; }

  async function loadSamples() {
    const slots = MODES[state.mode].slots;
    const files = await Promise.all(slots.map(async (slot) => {
      const blob = await (await fetch(SAMPLES[slot])).blob();
      return new File([blob], `specimen_${slot}.webp`, { type: "image/webp" });
    }));
    slots.forEach((slot, i) => setFile(slot, files[i], true));
    showDemoBanner(true);
  }

  function flash(msg) { $("#msg").textContent = msg || ""; }

  /* ---------------- mode ---------------- */
  function setMode(mode) {
    state.mode = mode;
    store.set("tocr.mode", mode);
    showDemoBanner(false);
    $$("[data-for]").forEach((el) => { el.style.display = el.dataset.for === mode ? "" : "none"; });
    flash("");
    renderDrops();
  }

  /* ---------------- run ---------------- */
  async function run(e) {
    e?.preventDefault();
    if (state.busy) return;
    const m = MODES[state.mode];
    const have = m.slots.filter((s) => state.files[s]);
    if (!have.length) return flash(t("need.files"));
    if (m.need === "both" && have.length < 2) return flash(t("need.both"));
    if (m.need === "all" && have.length < m.slots.length) return flash(t("need.files"));
    flash("");

    const fd = new FormData();
    for (const s of have) fd.append(s, state.files[s], state.files[s].name);
    const headers = {};
    const key = $("#apikey").value.trim();
    if (key) headers["X-API-Key"] = key;

    setBusy(true);
    const started = performance.now();
    const tick = setInterval(() => {
      const el = $("#elapsed");
      if (el) el.textContent = ((performance.now() - started) / 1000).toFixed(1) + " s";
    }, 100);
    const files = Object.fromEntries(have.map((s) => [s, state.urls[s]]));
    try {
      const res = await fetch(requestUrl(), { method: "POST", body: fd, headers });
      let body = null;
      try { body = await res.json(); } catch { /* not JSON */ }
      if (!res.ok) {
        state.result = null;
        state.error = { status: res.status, detail: body && (typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)) };
      } else {
        state.error = null;
        state.edits = {};
        state.result = { mode: state.mode, data: body, files };
      }
    } catch (err) {
      state.result = null;
      state.error = { status: 0, detail: String(err.message || err) };
    } finally {
      clearInterval(tick);
      setBusy(false);
      renderResult();
      if (innerWidth < 980) $("#result-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function setBusy(b) {
    state.busy = b;
    const btn = $("#run");
    btn.disabled = b;
    btn.classList.toggle("busy", b);
    btn.querySelector("[data-i18n]").textContent = t(b ? "btn.running" : "btn.run");
    if (b) {
      $("#result").innerHTML = `<div class="result-empty"><div class="progress"><i></i></div>
        <div><b>${esc(t("btn.running"))}</b> <span id="elapsed" style="font-family:var(--mono)">0.0 s</span></div>
        <div style="font-size:13px;margin-top:4px">${esc(t("res.wait"))}</div></div>`;
    }
  }

  /* ---------------- render: helpers ---------------- */
  function bar(v) {
    if (v == null) return "";
    const cls = v >= 0.8 ? "" : v >= 0.6 ? " mid" : " low";
    return `<div class="bar${cls}"><i><b style="width:${Math.round(v * 100)}%"></b></i><span>${Math.round(v * 100)}</span></div>`;
  }

  function fieldLabel(k) {
    const m = k.match(/^(.*)_(tg|en)$/);
    const base = m ? m[1] : k;
    const key = "f." + (PP_ALIAS[base] || base);
    const label = window.I18N[key] ? t(key) : k;
    return m ? `${label} <span style="color:var(--muted);font-size:12px">${m[2] === "tg" ? "Кир" : "Lat"}</span>` : label;
  }

  function warningsBlock(list) {
    if (!list || !list.length) return "";
    return `<div class="callout warn"><span>⚠️</span><div><b>${esc(t("res.warnings"))}</b><ul>${list.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div></div>`;
  }

  function actions(kinds) {
    const b = (act, key, cls = "btn-outline") => `<button type="button" class="btn btn-sm ${cls}" data-act="${act}">${esc(t(key))}</button>`;
    return `<div class="actions no-print">
      ${b("copy", "btn.copy", "btn-dark")}
      <span class="lbl">${esc(t("btn.download"))}</span>
      ${kinds.map((k) => b(k, "btn." + k)).join("")}
      ${b("print", "btn.print", "btn-ghost")}
    </div>`;
  }

  function fullJson(data) {
    return `<details class="sub no-print"><summary>${esc(t("res.full"))}</summary><pre class="mono-box">${esc(JSON.stringify(data, null, 2))}</pre></details>`;
  }

  /* ---------------- render: result ---------------- */
  function renderResult() {
    const box = $("#result");
    if (state.error) {
      const { status, detail } = state.error;
      const key = status === 0 ? "err.net" : window.I18N["err." + status] ? "err." + status : "err.other";
      box.innerHTML = `<div class="callout bad"><span>✕</span><div>
          <b>${status ? "HTTP " + status + " — " : ""}${esc(t(key))}</b>
          ${detail ? `<div class="sm">${esc(t("err.server"))}: ${esc(detail)}</div>` : ""}
          ${status === 422 ? `<div style="margin-top:6px"><a href="#tips">${esc(t("guide.title"))} →</a></div>` : ""}
          ${status === 401 ? `<div style="margin-top:6px"><a href="#adv" data-open-adv>${esc(t("opt.key"))} →</a></div>` : ""}
        </div></div>`;
      const a = box.querySelector("[data-open-adv]");
      if (a) a.addEventListener("click", () => { $("#adv").open = true; $("#apikey").focus(); });
      return;
    }
    if (!state.result) {
      box.innerHTML = `<div class="result-empty"><div>${esc(t("res.empty"))}</div></div>`;
      return;
    }
    const { mode, data } = state.result;
    if (mode === "hr") renderHr(box, data);
    else if (mode === "passport") renderPassport(box, data);
    else renderOcr(box, data);
    box.querySelectorAll("[data-act]").forEach((btn) => btn.addEventListener("click", () => act(btn.dataset.act, btn)));
  }

  function renderHr(box, d) {
    const review = new Set(d.needs_review || []);
    const rows = Object.keys(d.data).map((k) => {
      const v = k in state.edits ? state.edits[k] : d.data[k];
      const ph = NOT_ON_CARD.includes(k) ? t("res.notOnCard") : "—";
      const r = review.has(k);
      return `<tr class="${r ? "review" : ""}">
        <td class="k">${esc(t("f." + k))}<small>${k}</small></td>
        <td class="vc"><input class="v" data-k="${k}" value="${esc(v ?? "")}" placeholder="${esc(ph)}" title="${esc(v ?? "")}"></td>
        <td class="sc">${bar(d.scores?.[k])}</td>
        <td>${r ? `<span class="badge">● ${esc(t("res.review"))}</span>` : ""}</td></tr>`;
    }).join("");
    box.innerHTML = `
      <div class="res-head">
        <span class="chip">${esc(t("res.time"))}: ${(d.elapsed_ms / 1000).toFixed(1)} s</span>
        <span class="chip">lang: ${esc(d.lang)}</span>
        ${review.size ? `<span class="chip warn">needs_review: ${review.size}</span>` : `<span class="chip ok">✓ needs_review: 0</span>`}
      </div>
      ${review.size ? `<div class="callout warn"><span>👀</span><div>${esc(t("res.reviewNote"))}</div></div>`
                    : `<div class="callout ok"><span>✓</span><div>${esc(t("res.allGood"))}</div></div>`}
      ${warningsBlock(d.warnings)}
      <div class="table-wrap"><table class="res">
        <thead><tr><th>${esc(t("res.field"))}</th><th>${esc(t("res.value"))}</th><th>${esc(t("res.score"))}</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table></div>
      ${actions(["json", "csv"])}
      ${fullJson(d)}`;
    box.querySelectorAll("input.v").forEach((inp) => inp.addEventListener("input", () => { state.edits[inp.dataset.k] = inp.value; }));
  }

  function renderPassport(box, d) {
    const sides = Object.entries(d.sides || {}).map(([name, s]) => {
      const label = t(name === "back" ? "up.back" : name === "front" ? "up.front" : "up.image");
      return `<span class="chip ${s.recognized ? "ok" : "bad"}">${esc(label)}: ${esc(t(s.recognized ? "res.found" : "res.notFound"))}
        · ${esc(s.method)} · ${s.match_score}${s.rotated ? " · " + esc(t("res.rotated")) : ""}</span>`;
    }).join("");
    const rows = Object.entries(d.fields || {}).map(([k, f]) => {
      const check = f.verified === true ? `<span class="chip ok">✓ ${esc(t("res.ok"))}</span>`
        : f.verified === false ? `<span class="chip bad">✕ ${esc(t("res.conflict"))}</span>` : `<span style="color:var(--muted)">—</span>`;
      const raw = f.raw && f.raw !== f.value ? `<div style="font-size:12px;color:var(--muted);font-family:var(--mono)">${esc(t("res.raw"))}: ${esc(f.raw)}</div>` : "";
      const note = f.note ? `<div style="font-size:12px;color:var(--warn)">${esc(f.note)}</div>` : "";
      return `<tr class="${f.verified === false ? "review" : ""}">
        <td class="k">${fieldLabel(k)}<small>${k}</small></td>
        <td class="vc"><b style="font-weight:560">${esc(f.value ?? "—")}</b>${raw}${note}</td>
        <td class="sc">${bar(f.confidence)}</td><td>${check}</td></tr>`;
    }).join("");
    let mrz = "";
    if (d.mrz) {
      const checks = Object.entries(d.mrz.checks || {}).map(([k, ok]) => `<span class="chip ${ok ? "ok" : "bad"}">${ok ? "✓" : "✕"} ${esc(k)}</span>`).join(" ");
      mrz = `<h3 style="font-size:15px;margin:20px 0 6px">${esc(t("res.mrz"))}</h3>
        <div style="display:flex;gap:6px;flex-wrap:wrap">${checks}</div>
        ${d.mrz.lines ? `<pre class="mono-box">${esc(d.mrz.lines.join("\n"))}</pre>` : ""}`;
    }
    box.innerHTML = `
      <div class="res-head">
        <span class="chip">${esc(t("res.time"))}: ${(d.elapsed_ms / 1000).toFixed(1)} s</span>
        ${d.mrz ? `<span class="chip ${d.mrz.valid ? "ok" : "bad"}">${esc(t(d.mrz.valid ? "res.mrzValid" : "res.mrzInvalid"))}</span>` : ""}
      </div>
      <div class="res-head" style="margin-top:-6px">${sides}</div>
      ${warningsBlock(d.warnings)}
      <div class="table-wrap"><table class="res">
        <thead><tr><th>${esc(t("res.field"))}</th><th>${esc(t("res.value"))}</th><th>${esc(t("res.score"))}</th><th>${esc(t("res.check"))}</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
      ${mrz}
      ${actions(["json", "csv"])}
      ${fullJson(d)}`;
  }

  function renderOcr(box, d) {
    const text = "text" in state.edits ? state.edits.text : d.text;
    box.innerHTML = `
      <div class="res-head">
        <span class="chip">${esc(t("res.time"))}: ${(d.elapsed_ms / 1000).toFixed(1)} s</span>
        <span class="chip">${esc(d.engine)}</span>
        <span class="chip">${d.lines.length} ×</span>
        ${d.deskew_angle ? `<span class="chip">↻ ${d.deskew_angle.toFixed(1)}°</span>` : ""}
      </div>
      ${d.lines.length ? "" : `<div class="callout warn"><span>∅</span><div>${esc(t("res.noText"))}</div></div>`}
      <label class="lbl" for="ocr-text" style="font-size:13.5px;font-weight:600;display:block;margin-bottom:6px">${esc(t("res.text"))}</label>
      <textarea class="ocr-text" id="ocr-text" spellcheck="false">${esc(text)}</textarea>
      ${actions(["txt", "json"])}
      ${d.lines.length ? `<details class="sub" open><summary>${esc(t("res.boxes"))}</summary><div class="boxes"><canvas id="ocr-canvas"></canvas></div></details>` : ""}
      ${fullJson(d)}`;
    $("#ocr-text").addEventListener("input", (e) => { state.edits.text = e.target.value; });
    drawBoxes(d);
  }

  function drawBoxes(d) {
    const canvas = $("#ocr-canvas");
    const src = state.result.files.file;
    if (!canvas || !src) return;
    const img = new Image();
    img.onload = () => {
      // Server straightens with cv2: rotate by deskew_angle (counter-clockwise) on an expanded canvas
      const a = (d.deskew_angle || 0) * Math.PI / 180;
      const cos = Math.abs(Math.cos(a)), sin = Math.abs(Math.sin(a));
      const W = Math.floor(d.height * sin + d.width * cos), H = Math.floor(d.height * cos + d.width * sin);
      const scale = Math.min(1, 1400 / W);
      canvas.width = Math.round(W * scale);
      canvas.height = Math.round(H * scale);
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#111";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.translate(canvas.width / 2, canvas.height / 2);
      ctx.rotate(-a);
      ctx.drawImage(img, -d.width * scale / 2, -d.height * scale / 2, d.width * scale, d.height * scale);
      ctx.restore();
      ctx.lineWidth = 2;
      for (const ln of d.lines) {
        const c = ln.score >= 0.8 ? "46,139,87" : ln.score >= 0.6 ? "217,162,27" : "192,57,43";
        ctx.strokeStyle = `rgb(${c})`;
        ctx.fillStyle = `rgba(${c},.12)`;
        ctx.beginPath();
        ln.box.forEach(([x, y], i) => (i ? ctx.lineTo(x * scale, y * scale) : ctx.moveTo(x * scale, y * scale)));
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }
    };
    img.src = src;
  }

  /* ---------------- export ---------------- */
  function exportData() {
    const { mode, data } = state.result;
    if (mode === "hr") return { ...data, data: { ...data.data, ...state.edits } };
    if (mode === "ocr" && "text" in state.edits) return { ...data, text: state.edits.text };
    return data;
  }

  function csvCell(v) {
    const s = v == null ? "" : String(v);
    return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }

  function toCsv() {
    const { mode } = state.result;
    const d = exportData();
    let rows;
    if (mode === "hr") {
      const review = new Set(d.needs_review || []);
      rows = [["field", "label", "value", "score", "needs_review"],
        ...Object.entries(d.data).map(([k, v]) => [k, t("f." + k), v, d.scores?.[k] ?? "", review.has(k) ? "1" : ""])];
    } else {
      rows = [["field", "value", "raw", "confidence", "verified", "note"],
        ...Object.entries(d.fields).map(([k, f]) => [k, f.value, f.raw, f.confidence, f.verified, f.note])];
    }
    // ";" + BOM: opens correctly in Excel with Cyrillic and CIS regional settings
    return "﻿" + rows.map((r) => r.map(csvCell).join(";")).join("\r\n");
  }

  function download(name, text, type) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type }));
    a.download = name;
    document.body.append(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }

  async function copyText(text, btn) {
    try { await navigator.clipboard.writeText(text); } catch {
      const ta = Object.assign(document.createElement("textarea"), { value: text });
      document.body.append(ta); ta.select(); document.execCommand("copy"); ta.remove();
    }
    if (btn) {
      const old = btn.textContent;
      btn.textContent = t("btn.copied");
      setTimeout(() => { btn.textContent = old; }, 1400);
    }
  }

  function act(kind, btn) {
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    const { mode } = state.result;
    const d = exportData();
    if (kind === "copy") return copyText(mode === "ocr" ? d.text : JSON.stringify(d, null, 2), btn);
    if (kind === "json") return download(`tajik-ocr-${mode}-${stamp}.json`, JSON.stringify(d, null, 2), "application/json");
    if (kind === "csv") return download(`tajik-ocr-${mode}-${stamp}.csv`, toCsv(), "text/csv;charset=utf-8");
    if (kind === "txt") return download(`tajik-ocr-${stamp}.txt`, d.text, "text/plain;charset=utf-8");
    if (kind === "print") return print();
  }

  /* ---------------- code snippets ---------------- */
  function renderCode() {
    const mode = state.mode;
    const o = opts();
    const url = requestUrl(mode, o);
    const hasKey = !!$("#apikey").value.trim();
    // /passport accepts one side: show only the uploaded ones (or both when nothing is uploaded yet)
    const filled = MODES[mode].slots.filter((s) => state.files[s]);
    const used = mode === "passport" && filled.length ? filled : MODES[mode].slots;
    const fname = (s) => state.files[s]?.name || SLOT[s].file;
    let code = "";
    if (state.codeLang === "curl") {
      code = `curl.exe -X POST ${hasKey ? '-H "X-API-Key: YOUR_KEY" ' : ""}\`\n` +
        used.map((s) => `  -F "${s}=@${fname(s)}" \``).join("\n") + `\n  "${url}"`;
      code = "# Windows PowerShell (Linux/macOS: curl + \\)\n" + code;
    } else if (state.codeLang === "python") {
      code = `import requests\n\nfiles = {\n` +
        used.map((s) => `    "${s}": open("${fname(s)}", "rb"),`).join("\n") + `\n}\n` +
        `r = requests.post(\n    "${url}",\n    files=files,\n` + (hasKey ? `    headers={"X-API-Key": "YOUR_KEY"},\n` : "") +
        `    timeout=60,\n)\nr.raise_for_status()\n` +
        (mode === "hr" ? `record = r.json()\nprint(record["data"], record["needs_review"])` : mode === "ocr" ? `print(r.json()["text"])` : `print(r.json()["fields"])`);
    } else if (state.codeLang === "php") {
      code = `use Illuminate\\Support\\Facades\\Http;\n\n$response = Http::timeout(60)\n` +
        (hasKey ? `    ->withHeaders(['X-API-Key' => config('services.tajik_ocr.key')])\n` : "") +
        used.map((s) => `    ->attach('${s}', fopen($request->file('${s}')->path(), 'r'), '${fname(s)}')`).join("\n") +
        `\n    ->post('${url}')\n    ->throw();\n\n` +
        (mode === "hr" ? `$employee = $response->json('data');      // 18 fields\n$review   = $response->json('needs_review'); // check by eye`
          : mode === "ocr" ? `$text = $response->json('text');` : `$fields = $response->json('fields');`);
    } else {
      code = `const fd = new FormData();\n` +
        used.map((s) => `fd.append("${s}", ${s}Input.files[0]);`).join("\n") +
        `\n\nconst res = await fetch("${url}", {\n  method: "POST",\n  body: fd,\n` +
        (hasKey ? `  headers: { "X-API-Key": "YOUR_KEY" },\n` : "") +
        `});\nif (!res.ok) throw new Error((await res.json()).detail);\nconst data = await res.json();`;
    }
    $("#code").textContent = code;
    $$("#code-tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.lang === state.codeLang)));
  }

  /* ---------------- server status ---------------- */
  async function checkHealth() {
    const el = $("#status");
    const label = el.querySelector("[data-i18n]");
    try {
      const r = await fetch("/health", { cache: "no-store" });
      const h = await r.json();
      el.className = "pill status on";
      label.dataset.i18n = "status.online";
      label.textContent = t("status.online");
      el.title = `engine: ${h.default_engine}`;
    } catch {
      el.className = "pill status off";
      label.dataset.i18n = "status.offline";
      label.textContent = t("status.offline");
    }
  }

  /* ---------------- init ---------------- */
  document.addEventListener("DOMContentLoaded", () => {
    const form = $("#form");
    const savedMode = store.get("tocr.mode");
    if (savedMode && MODES[savedMode]) form.mode.value = savedMode;
    $$('input[name="mode"]').forEach((r) => r.addEventListener("change", () => setMode(r.value)));
    form.addEventListener("submit", run);
    form.addEventListener("change", renderCode);
    form.addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) run(e); });
    $("#min_score").addEventListener("input", (e) => { $("#min_out").textContent = Number(e.target.value).toFixed(2); });

    // API key: only kept if "remember" is on
    const savedKey = store.get("tocr.key");
    if (savedKey) { $("#apikey").value = savedKey; $("#key-remember").checked = true; }
    const saveKey = () => {
      if ($("#key-remember").checked && $("#apikey").value.trim()) store.set("tocr.key", $("#apikey").value.trim());
      else store.del("tocr.key");
      renderCode();
    };
    $("#apikey").addEventListener("input", saveKey);
    $("#key-remember").addEventListener("change", saveKey);
    $("#key-show").addEventListener("click", () => {
      const i = $("#apikey");
      i.type = i.type === "password" ? "text" : "password";
    });

    $("#reset").addEventListener("click", () => {
      Object.keys(state.files).forEach((s) => setFile(s, null));
      state.result = null; state.error = null; state.edits = {};
      renderResult();
    });

    $$("#code-tabs button").forEach((b) => b.addEventListener("click", () => {
      state.codeLang = b.dataset.lang; store.set("tocr.code", state.codeLang); renderCode();
    }));
    $("#code-copy").addEventListener("click", (e) => copyText($("#code").textContent, e.currentTarget));

    window.Site.onLang(() => { renderDrops(); if (state.result || state.error) renderResult(); });
    $("#sample-btn").addEventListener("click", () => loadSamples().catch(() => flash(t("err.net"))));

    // /try?demo=hr|passport|ocr: load the sample and run it right away
    const demo = new URLSearchParams(location.search).get("demo");
    if (demo && MODES[demo]) form.mode.value = demo;
    setMode(form.mode.value);
    checkHealth();
    if (demo && MODES[demo]) {
      loadSamples().then(() => run()).catch(() => flash(t("err.net")));
      const u = new URL(location.href);
      u.searchParams.delete("demo"); // a reload should not re-run the demo
      history.replaceState(null, "", u);
    }
  });
})();
