"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const state = { data: null, i18n: null, lang: null, kind: "", mag: 0, offline: false };
  const params = new URLSearchParams(location.search);

  const tr = () => state.i18n[state.lang] || state.i18n.en;
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function ago(iso) {
    const s = tr(), min = Math.round((Date.now() - Date.parse(iso)) / 60000);
    if (min < 1) return s.now;
    if (min < 60) return s.ago_m.replace("{n}", min);
    if (min < 48 * 60) return s.ago_h.replace("{n}", Math.round(min / 60));
    return s.ago_d.replace("{n}", Math.round(min / 1440));
  }

  function fmt(iso) {
    const tz = state.data.site.timezone || "UTC";
    try {
      return new Intl.DateTimeFormat(state.lang, {
        day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: tz, timeZoneName: "short" }).format(new Date(iso));
    } catch { return iso; }
  }

  function options() {
    const s = tr(), d = state.data;
    $("lang").innerHTML = d.site.languages.filter((l) => state.i18n[l])
      .map((l) => `<option value="${l}"${l === state.lang ? " selected" : ""}>${esc(state.i18n[l].name)}</option>`).join("");
    const kinds = [...new Set(d.alerts.map((a) => a.kind))];
    $("kind").innerHTML = [`<option value="">${esc(s.all)}</option>`]
      .concat(kinds.map((k) => `<option value="${k}"${k === state.kind ? " selected" : ""}>${esc(s.kind[k] || k)}</option>`)).join("");
    $("kind").hidden = kinds.length < 2;
    $("mag").innerHTML = [0, 2, 3, 4, 5, 6].map((m) =>
      `<option value="${m}"${m === state.mag ? " selected" : ""}>${m ? s.min_mag + " " + m : s.kind.earthquake + ": " + s.all}</option>`).join("");
    $("mag").hidden = !kinds.includes("earthquake");
  }

  function render() {
    const s = tr(), d = state.data;
    document.documentElement.lang = state.lang;
    document.documentElement.dir = s.dir;
    options();
    const rows = d.alerts.filter((a) => (!state.kind || a.kind === state.kind) &&
      (a.kind !== "earthquake" || a.magnitude == null || a.magnitude >= state.mag));
    $("list").innerHTML = rows.length ? rows.map((a) => {
      const quake = a.kind === "earthquake" && a.magnitude != null;
      const badge = quake ? a.magnitude.toFixed(1) : esc((s.severity[a.severity] || "").slice(0, 8));
      const head = (s.kind[a.kind] || s.kind.other) + " — " + (a.area || a.title);
      const parts = [`<time datetime="${a.time}" title="${esc(fmt(a.time))}">${esc(fmt(a.time))} · ${esc(ago(a.time))}</time>`];
      if (a.depth_km != null) parts.push(`${esc(s.depth)} ${Math.round(a.depth_km)} ${esc(s.km)}`);
      if (a.expires) parts.push(`${esc(s.expires)} ${esc(fmt(a.expires))}`);
      const srcs = a.reports.map((r) => {
        const label = esc(r.source.toUpperCase()) + (quake && r.magnitude != null ? " " + Number(r.magnitude).toFixed(1) : "");
        return r.url ? `<a href="${esc(r.url)}" rel="noopener">${label}</a>` : label;
      }).join(", ");
      return `<article class="alert ${esc(a.severity)}"><div class="badge">${badge}</div><div>
        <h2>${a.url ? `<a href="${esc(a.url)}" rel="noopener">${esc(head)}</a>` : esc(head)}</h2>
        <p class="meta">${parts.join(" · ")}</p><p class="meta">${esc(s.sources)}: ${srcs}</p></div></article>`;
    }).join("") : `<p class="muted">${esc(s.empty)}</p>`;
    $("updated").textContent = `${s.updated}: ${fmt(d.generated)} (${ago(d.generated)}) · ${d.generator}`;
    $("status-title").textContent = s.source_status;
    $("status").innerHTML = d.sources.map((x) => x.ok
      ? `<li>${esc(x.name)}: ${esc(s.ok)} (${x.count})</li>`
      : `<li class="bad">${esc(x.name)}: ${esc(s.failed)}</li>`).join("");
    $("feed").textContent = s.feed;
    $("disclaimer").textContent = s.disclaimer;
    const staleMin = (Date.now() - Date.parse(d.generated)) / 60000;
    const limit = 3 * (d.site.refresh_minutes || 5) + 15; // scheduled Actions runs are often late
    const msg = state.offline ? s.offline : staleMin > limit ? s.stale : "";
    $("banner").textContent = msg;
    $("banner").hidden = !msg;
    $("install").textContent = s.install;
  }

  async function load() {
    try {
      const res = await fetch("alerts.json", { cache: "no-store" });
      state.data = await res.json();
      state.offline = res.headers.get("x-from-cache") === "1" || !navigator.onLine;
    } catch {
      state.offline = true;
      if (!state.data) { $("list").innerHTML = '<p class="muted">alerts.json?</p>'; return; }
    }
    if (!state.lang) {
      const avail = state.data.site.languages;
      const wanted = [params.get("lang"), localStorage.getItem("lang"), ...(navigator.languages || [])]
        .filter(Boolean).map((l) => l.slice(0, 2));
      state.lang = wanted.find((l) => avail.includes(l) && state.i18n[l]) || state.data.site.default_language;
    }
    render();
  }

  $("lang").addEventListener("change", (e) => { state.lang = e.target.value; localStorage.setItem("lang", state.lang); render(); });
  $("kind").addEventListener("change", (e) => { state.kind = e.target.value; render(); });
  $("mag").addEventListener("change", (e) => { state.mag = Number(e.target.value); render(); });
  window.addEventListener("online", load);
  window.addEventListener("offline", () => { state.offline = true; if (state.data) render(); });

  let deferred = null;
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferred = e; $("install").hidden = false; });
  $("install").addEventListener("click", () => { if (deferred) { deferred.prompt(); deferred = null; $("install").hidden = true; } });

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
  fetch("i18n.json").then((r) => r.json()).then((i) => { state.i18n = i; load(); setInterval(load, 120000); });
})();
