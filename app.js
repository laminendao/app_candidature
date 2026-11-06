(() => {
  "use strict";

  const TYPES = { all: "Tout", ens: "Enseignement / EC", pd: "Postdoc", ds: "Data scientist", da: "Data analyst" };
  const FIT = { hi: "Très bon fit", mid: "Fit correct", lo: "Fit partiel" };
  const FIT_RANK = { hi: 0, mid: 1, lo: 2 };
  const STATUSES = ["À regarder", "À préparer", "Envoyée", "Entretien", "Refus", "Écartée"];
  const CLOSED = new Set(["Refus", "Écartée"]);
  const KEY_TRACK = "suivi-candidatures:track";
  const KEY_CUSTOM = "suivi-candidatures:custom";
  const KEY_THEME = "suivi-candidatures:theme";
  const DAY = 86400000;

  // ---------- stockage ----------
  const load = (k, fallback) => { try { return JSON.parse(localStorage.getItem(k)) ?? fallback; } catch { return fallback; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { toast("Sauvegarde impossible dans ce navigateur"); } };

  let track = load(KEY_TRACK, {});      // { id: { status, notes, updated } }
  let custom = load(KEY_CUSTOM, []);    // offres ajoutées depuis l'interface
  const state = { type: "all", q: "", status: "", sort: "fit" };

  const base = Array.isArray(window.OFFRES) ? window.OFFRES : [];
  const allOffers = () => [...base, ...custom.map(o => ({ ...o, mine: true }))];

  // ---------- utilitaires ----------
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const today = () => { const d = new Date(); d.setHours(0, 0, 0, 0); return d; };
  const parseDate = s => { if (!s) return null; const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
  const fmtDate = s => { const d = parseDate(s); return d ? d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" }) : ""; };
  const daysLeft = o => { const d = parseDate(o.deadline); return d ? Math.round((d - today()) / DAY) : null; };
  const statusOf = id => track[id]?.status || STATUSES[0];
  const safeUrl = u => /^https?:\/\//i.test(u || "") ? u : "";

  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg; t.hidden = false;
    clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 2400);
  }

  function deadlineBadge(o) {
    const n = daysLeft(o);
    if (n === null) return "";
    if (n < 0) return `<span class="pill warn">Clôturée</span>`;
    if (n === 0) return `<span class="pill warn">Dernier jour</span>`;
    if (n <= 7) return `<span class="pill warn">J-${n}</span>`;
    return `<span class="pill lo">J-${n}</span>`;
  }

  // ---------- rendu ----------
  function renderChips() {
    const offers = allOffers();
    $("#chips").innerHTML = Object.entries(TYPES).map(([k, label]) => {
      const count = k === "all" ? offers.length : offers.filter(o => o.type === k).length;
      return `<button class="chip" type="button" data-type="${k}" aria-pressed="${state.type === k}">${label}<small>${count}</small></button>`;
    }).join("");
  }

  function renderStats() {
    const offers = allOffers();
    const by = s => offers.filter(o => statusOf(o.id) === s).length;
    const urgent = offers.filter(o => { const n = daysLeft(o); return n !== null && n >= 0 && n <= 7 && !["Envoyée", "Entretien"].includes(statusOf(o.id)) && !CLOSED.has(statusOf(o.id)); }).length;
    const items = [
      ["Offres suivies", offers.length, ""],
      ["À préparer", by("À préparer"), ""],
      ["Envoyées", by("Envoyée") + by("Entretien"), ""],
      ["Date limite sous 7 jours", urgent, urgent ? "alert" : ""]
    ];
    $("#stats").innerHTML = items.map(([l, v, c]) => `<div class="stat ${c}"><b>${v}</b><span>${l}</span></div>`).join("");
  }

  function filtered() {
    const q = state.q.trim().toLowerCase();
    let list = allOffers().filter(o =>
      (state.type === "all" || o.type === state.type) &&
      (!state.status || statusOf(o.id) === state.status) &&
      (!q || [o.org, o.title, o.location, o.contract, o.why].join(" ").toLowerCase().includes(q))
    );
    const closedLast = (a, b) => CLOSED.has(statusOf(a.id)) - CLOSED.has(statusOf(b.id));
    const sorts = {
      fit: (a, b) => closedLast(a, b) || FIT_RANK[a.fit] - FIT_RANK[b.fit] || (b.published || "").localeCompare(a.published || ""),
      deadline: (a, b) => {
        const da = daysLeft(a), db = daysLeft(b);
        const ka = da === null ? 1e6 : da < 0 ? 1e5 + -da : da;
        const kb = db === null ? 1e6 : db < 0 ? 1e5 + -db : db;
        return closedLast(a, b) || ka - kb;
      },
      published: (a, b) => (b.published || "").localeCompare(a.published || "")
    };
    return list.sort(sorts[state.sort]);
  }

  function card(o) {
    const st = statusOf(o.id);
    const notes = track[o.id]?.notes || "";
    const url = safeUrl(o.url);
    const dl = o.deadline ? `Date limite ${fmtDate(o.deadline)}` : "Pas de date limite affichée";
    return `<article class="job ${CLOSED.has(st) ? "closed" : ""}" data-id="${esc(o.id)}">
      <div class="head"><span class="org">${esc(o.org)}</span><h3 class="title">${esc(o.title)}</h3></div>
      <div class="badges">${o.mine ? `<span class="pill mine">Ajoutée</span>` : ""}${deadlineBadge(o)}<span class="pill ${esc(o.fit)}">${FIT[o.fit] || ""}</span></div>
      <div class="meta">
        ${o.location ? `<span>${esc(o.location)}</span>` : ""}
        ${o.contract ? `<span>${esc(o.contract)}</span>` : ""}
        <span class="mono">${dl}</span>
        ${o.published ? `<span class="mono">Publiée le ${fmtDate(o.published)}</span>` : ""}
      </div>
      ${o.why ? `<p class="why">${esc(o.why)}</p>` : ""}
      ${o.contact ? `<div class="contact">Contact : <span class="mono">${esc(o.contact)}</span><button class="link-btn" type="button" data-copy="${esc(o.contact)}">Copier</button></div>` : ""}
      <details class="notes" ${notes ? "open" : ""}>
        <summary>Mes notes</summary>
        <textarea id="notes-${esc(o.id)}" data-notes="${esc(o.id)}" rows="3" placeholder="Relances, interlocuteurs, prochaines étapes…">${esc(notes)}</textarea>
      </details>
      <div class="foot">
        ${url ? `<a href="${esc(url)}" target="_blank" rel="noopener">Voir l'offre ↗</a>` : `<span></span>`}
        <div class="right">
          ${o.mine ? `<button class="btn danger" type="button" data-del="${esc(o.id)}">Supprimer</button>` : ""}
          <label>Statut <select id="status-${esc(o.id)}" data-status="${esc(o.id)}">${STATUSES.map(s => `<option${s === st ? " selected" : ""}>${s}</option>`).join("")}</select></label>
        </div>
      </div>
    </article>`;
  }

  function renderList() {
    const list = filtered();
    $("#list").innerHTML = list.length
      ? list.map(card).join("")
      : `<div class="empty">Aucune offre ne correspond à ces filtres.</div>`;
  }

  function render() { renderChips(); renderStats(); renderList(); }

  // ---------- statut / notes ----------
  function setTrack(id, patch) {
    track[id] = { ...track[id], ...patch, updated: new Date().toISOString() };
    save(KEY_TRACK, track);
  }

  // ---------- événements ----------
  $("#chips").addEventListener("click", e => {
    const b = e.target.closest("[data-type]"); if (!b) return;
    state.type = b.dataset.type; render();
  });
  $("#q").addEventListener("input", e => { state.q = e.target.value; renderList(); });
  $("#sort").addEventListener("change", e => { state.sort = e.target.value; renderList(); });
  $("#f-status").innerHTML = `<option value="">Tous</option>` + STATUSES.map(s => `<option>${s}</option>`).join("");
  $("#f-status").addEventListener("change", e => { state.status = e.target.value; renderList(); });

  $("#list").addEventListener("change", e => {
    const id = e.target.dataset.status;
    if (id) { setTrack(id, { status: e.target.value }); render(); toast(`Statut : ${e.target.value}`); }
  });
  $("#list").addEventListener("input", e => {
    const id = e.target.dataset.notes;
    if (id) { clearTimeout(setTrack.t); setTrack.t = setTimeout(() => setTrack(id, { notes: e.target.value }), 400); }
  });
  $("#list").addEventListener("click", async e => {
    const c = e.target.closest("[data-copy]");
    if (c) {
      try { await navigator.clipboard.writeText(c.dataset.copy); toast("Adresse copiée"); }
      catch { const r = document.createRange(); r.selectNodeContents(c.previousElementSibling); getSelection().removeAllRanges(); getSelection().addRange(r); toast("Adresse sélectionnée : Ctrl+C"); }
      return;
    }
    const d = e.target.closest("[data-del]");
    if (d) {
      if (d.dataset.armed) {
        custom = custom.filter(o => o.id !== d.dataset.del);
        delete track[d.dataset.del];
        save(KEY_CUSTOM, custom); save(KEY_TRACK, track); render(); toast("Offre supprimée");
      } else {
        d.dataset.armed = "1"; d.textContent = "Confirmer la suppression";
        setTimeout(() => { if (d.isConnected) { delete d.dataset.armed; d.textContent = "Supprimer"; } }, 3000);
      }
    }
  });

  // ---------- ajout ----------
  const dlg = $("#dlg");
  $("#btn-add").addEventListener("click", () => { $("#form").reset(); dlg.showModal(); $("#i-title").focus(); });
  $("#btn-cancel").addEventListener("click", () => dlg.close());
  $("#form").addEventListener("submit", e => {
    e.preventDefault();
    const v = id => $(id).value.trim();
    const slug = (v("#i-org") + "-" + v("#i-title")).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").slice(0, 40);
    const offer = {
      id: `${slug}-${Date.now().toString(36)}`,
      type: v("#i-type"), fit: v("#i-fit"),
      org: v("#i-org"), title: v("#i-title"), location: v("#i-location"), contract: v("#i-contract"),
      deadline: v("#i-deadline") || null, published: new Date().toISOString().slice(0, 10),
      why: v("#i-why"), contact: v("#i-contact"), url: v("#i-url")
    };
    custom.push(offer); save(KEY_CUSTOM, custom);
    dlg.close(); render(); toast("Offre ajoutée");
  });

  // ---------- export / import ----------
  function download(name, text, type) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type }));
    a.download = name; document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }
  $("#btn-export").addEventListener("click", () => {
    const stamp = new Date().toISOString().slice(0, 10);
    download(`suivi-${stamp}.json`, JSON.stringify({ version: 1, exported: new Date().toISOString(), track, custom }, null, 2), "application/json");
    toast("Suivi exporté");
  });
  $("#file-import").addEventListener("change", async e => {
    const f = e.target.files[0]; if (!f) return;
    try {
      const data = JSON.parse(await f.text());
      if (typeof data.track !== "object" || !Array.isArray(data.custom)) throw new Error();
      track = { ...track, ...data.track };
      const ids = new Set(custom.map(o => o.id));
      custom = [...custom, ...data.custom.filter(o => o && o.id && !ids.has(o.id))];
      save(KEY_TRACK, track); save(KEY_CUSTOM, custom); render(); toast("Suivi importé");
    } catch { toast("Fichier non reconnu : choisis un export de cette application"); }
    e.target.value = "";
  });
  $("#btn-offres").addEventListener("click", () => {
    const all = [...base, ...custom];
    const header = "// Liste des offres suivies. Voir README.md pour le format des champs.\n\n";
    download("offres.js", header + "window.OFFRES = " + JSON.stringify(all, null, 2) + ";\n", "text/javascript");
    toast("offres.js téléchargé : remplace data/offres.js dans le dépôt");
  });

  // ---------- thème ----------
  const applyTheme = t => { if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme; };
  applyTheme(load(KEY_THEME, null));
  $("#btn-theme").addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    applyTheme(next); save(KEY_THEME, next);
  });

  if (!base.length) toast("data/offres.js introuvable ou vide");
  render();
})();
