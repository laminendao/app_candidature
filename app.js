(() => {
  "use strict";

  // ------------------------------------------------------------------ constantes
  const FIT = { hi: "Très bon fit", mid: "Fit correct", lo: "Fit partiel" };
  const STATUSES = ["À regarder", "À préparer", "Envoyée", "Entretien", "Refus", "Écartée"];
  const HIDDEN = new Set(["Refus", "Écartée"]);
  const IDF = new Set(["75", "77", "78", "91", "92", "93", "94", "95"]);
  const IDF_RE = /\b(paris|ile-de-france|île-de-france|essonne|hauts-de-seine|yvelines|val-de-marne|seine-saint-denis|val-d'oise|seine-et-marne|\(?(75|77|78|91|92|93|94|95)\)?)\b/i;
  const NEW_DAYS = 2;
  const PAGE = 30;
  const DAY = 86400000;
  const STATE_LABEL = { ok: ["OK", "hi"], warning: ["Partiel", "mid"], error: ["Erreur", "warn"], skipped: ["Non configurée", "lo"], blocked: ["Interdite (robots.txt)", "warn"], disabled: ["Désactivée", "lo"] };

  // ------------------------------------------------------------------ état
  const S = {
    profile: null, profiles: [], meta: null, offers: [], status: null,
    track: {}, custom: [],
    f: { cat: "all", q: "", status: "", source: "", sort: "score", onlyNew: false, idf: false, hide: true, gone: false },
    shown: PAGE, tab: "offres",
  };

  // ------------------------------------------------------------------ utilitaires
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const safeUrl = u => /^https?:\/\//i.test(u || "") ? u : "";
  const store = {
    get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { toast("Sauvegarde impossible dans ce navigateur"); } },
  };
  const key = what => `suivi:${S.profile}:${what}`;
  const today = () => { const d = new Date(); d.setHours(0, 0, 0, 0); return d; };
  const parseDate = s => { if (!s) return null; const [y, m, d] = s.slice(0, 10).split("-").map(Number); return new Date(y, m - 1, d); };
  const fmtDate = s => { const d = parseDate(s); return d ? d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" }) : ""; };
  const daysFrom = s => { const d = parseDate(s); return d ? Math.round((d - today()) / DAY) : null; };
  const statusOf = uid => S.track[uid]?.status || STATUSES[0];
  const isNew = o => o.source !== "manuel" && o.first_seen && -daysFrom(o.first_seen) < NEW_DAYS;
  const inIdf = o => IDF.has(o.department) || IDF_RE.test(o.location || "");

  function toast(msg) {
    const t = $("#toast"); t.textContent = msg; t.hidden = false;
    clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 2600);
  }

  async function getJSON(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`${url} : ${r.status}`);
    return r.json();
  }

  // ------------------------------------------------------------------ chargement
  async function boot() {
    try {
      const idx = await getJSON("data/profiles.json");
      S.profiles = idx.profiles || [];
      if (!S.profiles.length) throw new Error("aucun profil dans data/profiles.json");
      const wanted = new URLSearchParams(location.search).get("p") || store.get("suivi:profil", null);
      S.profile = S.profiles.some(p => p.id === wanted) ? wanted : S.profiles[0].id;
      const sel = $("#profile");
      sel.innerHTML = S.profiles.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("");
      sel.value = S.profile;
      $("#profile-wrap").hidden = S.profiles.length < 2;
      S.status = await getJSON("data/status.json").catch(() => null);
      await loadProfile();
    } catch (e) {
      const local = location.protocol === "file:";
      $("#error").hidden = false;
      $("#error").innerHTML = local
        ? "Le navigateur bloque la lecture des données quand la page est ouverte comme fichier. Lance <code>python3 -m http.server</code> dans le dossier, puis ouvre <code>http://localhost:8000</code>."
        : `Impossible de charger les données (${esc(e.message)}). Le collecteur a-t-il déjà tourné ?`;
      $("#updated").textContent = "";
    }
  }

  async function loadProfile() {
    const base = `data/profiles/${encodeURIComponent(S.profile)}/`;
    const [meta, data] = await Promise.all([getJSON(base + "meta.json"), getJSON(base + "offres.json")]);
    S.meta = meta; S.offers = data.offres || [];
    S.track = store.get(key("track"), {});
    S.custom = store.get(key("custom"), []);
    store.set("suivi:profil", S.profile);
    const when = data.generated ? new Date(data.generated).toLocaleString("fr-FR", { dateStyle: "long", timeStyle: "short" }) : "jamais";
    $("#updated").textContent = `Profil : ${meta.name} · dernière collecte : ${when}`;
    document.title = `Suivi des candidatures – ${meta.name}`;
    $("#i-category").innerHTML = meta.categories.map(c => `<option value="${esc(c.id)}">${esc(c.label)}</option>`).join("");
    S.f.cat = "all"; S.shown = PAGE;
    renderAll();
    setupBookmarklet();
    openFromBookmarklet();
  }

  // ------------------------------------------------------------------ bouton « Ajouter au radar »
  function setupBookmarklet() {
    const app = location.origin + location.pathname;
    const code = `(()=>{const s=String(getSelection()).slice(0,600);window.open(${JSON.stringify(app)}+"?p=${encodeURIComponent(S.profile)}&add=1&t="+encodeURIComponent(document.title)+"&u="+encodeURIComponent(location.href)+"&s="+encodeURIComponent(s),"_blank")})()`;
    const a = $("#bookmarklet");
    a.href = "javascript:" + code;
    a.onclick = e => { e.preventDefault(); toast("Fais-le glisser dans ta barre de favoris"); };
    $("#btn-bm-copy").onclick = async () => {
      try { await navigator.clipboard.writeText(a.href); toast("Code copié : colle-le comme adresse d'un nouveau favori"); }
      catch { toast("Copie impossible : sélectionne le bouton ＋ Radar → clic droit → Copier l'adresse du lien"); }
    };
  }

  function openFromBookmarklet() {
    const q = new URLSearchParams(location.search);
    if (q.get("add") !== "1") return;
    let title = (q.get("t") || "").replace(/\s*[|·–-]\s*(LinkedIn|Indeed|Welcome to the Jungle|APEC|Hellowork|Glassdoor|JobTeaser)\b.*$/i, "").trim();
    let org = "";
    const m = title.match(/^(.*?)\s+(?:chez|at|@)\s+(.+)$/i);   // « Data Scientist chez Safran »
    if (m) { title = m[1]; org = m[2]; }
    $("#form").reset();
    $("#i-title").value = title;
    $("#i-org").value = org;
    $("#i-url").value = q.get("u") || "";
    $("#i-why").value = (q.get("s") || "").trim();
    switchTab("offres");
    $("#dlg").showModal();
    (org ? $("#i-location") : $("#i-org")).focus();
    const clean = new URL(location.href);
    ["add", "t", "u", "s"].forEach(k => clean.searchParams.delete(k));
    history.replaceState(null, "", clean);
  }

  // ------------------------------------------------------------------ données combinées
  function allOffers() {
    const feed = new Map(S.offers.map(o => [o.uid, o]));
    const mine = S.custom.map(o => ({ ...o, mine: true }));
    // Offres suivies qui ont disparu du flux : on garde la copie enregistrée
    const archived = Object.entries(S.track)
      .filter(([uid, t]) => !feed.has(uid) && t.snapshot && t.status && t.status !== STATUSES[0] && !mine.some(m => m.uid === uid))
      .map(([uid, t]) => ({ ...t.snapshot, uid, active: false, archived: true }));
    return [...S.offers, ...mine, ...archived];
  }

  function filtered() {
    const f = S.f, q = f.q.trim().toLowerCase();
    const list = allOffers().filter(o => {
      const st = statusOf(o.uid);
      if (f.cat !== "all" && o.category !== f.cat) return false;
      if (f.status && st !== f.status) return false;
      if (f.source && o.source !== f.source) return false;
      if (f.onlyNew && !isNew(o)) return false;
      if (f.idf && !inIdf(o)) return false;
      if (f.hide && !f.status && HIDDEN.has(st)) return false;
      if (!f.gone && o.active === false && st === STATUSES[0]) return false;
      if (q && ![o.title, o.org, o.location, o.contract, o.description, o.why, (o.reasons || []).join(" ")].join(" ").toLowerCase().includes(q)) return false;
      return true;
    });
    const dl = o => { const n = daysFrom(o.deadline); return n === null ? 1e6 : n < 0 ? 1e5 - n : n; };
    const sorts = {
      score: (a, b) => (b.score || 0) - (a.score || 0) || (b.published || "").localeCompare(a.published || ""),
      recent: (a, b) => (b.first_seen || b.published || "").localeCompare(a.first_seen || a.published || "") || (b.score || 0) - (a.score || 0),
      deadline: (a, b) => dl(a) - dl(b) || (b.score || 0) - (a.score || 0),
    };
    return list.sort(sorts[f.sort]);
  }

  // ------------------------------------------------------------------ rendu : offres
  function renderStats() {
    const all = allOffers().filter(o => o.active !== false);
    const n = s => Object.values(S.track).filter(t => t.status === s).length;
    const items = [
      ["Nouvelles (48 h)", all.filter(isNew).length, "new"],
      ["Très bon fit", all.filter(o => o.fit === "hi").length, ""],
      ["À préparer", n("À préparer"), ""],
      ["Envoyées", n("Envoyée") + n("Entretien"), ""],
    ];
    $("#stats").innerHTML = items.map(([l, v, c]) => `<div class="stat ${c}"><b>${v}</b><span>${l}</span></div>`).join("");
  }

  function renderFilters() {
    const all = allOffers().filter(o => o.active !== false);
    const cats = [{ id: "all", label: "Tout" }, ...S.meta.categories];
    $("#chips").innerHTML = cats.map(c => {
      const count = c.id === "all" ? all.length : all.filter(o => o.category === c.id).length;
      if (c.id !== "all" && !count) return "";
      return `<button class="chip" type="button" data-cat="${esc(c.id)}" aria-pressed="${S.f.cat === c.id}">${esc(c.label)}<small>${count}</small></button>`;
    }).join("");
    const sources = [...new Map(allOffers().map(o => [o.source, o.source_label || (o.mine ? "Ajoutée à la main" : o.source)])).entries()];
    const curSrc = S.f.source;
    $("#f-source").innerHTML = `<option value="">Toutes</option>` + sources.map(([id, l]) => `<option value="${esc(id)}">${esc(l)}</option>`).join("");
    $("#f-source").value = curSrc;
    $("#n-offres").textContent = all.length;
  }

  function deadlineBadge(o) {
    const n = daysFrom(o.deadline);
    if (n === null) return "";
    if (n < 0) return `<span class="pill warn">Clôturée</span>`;
    if (n <= 7) return `<span class="pill warn">${n === 0 ? "Dernier jour" : "J-" + n}</span>`;
    return `<span class="pill lo">J-${n}</span>`;
  }

  function card(o) {
    const st = statusOf(o.uid);
    const notes = S.track[o.uid]?.notes || "";
    const url = safeUrl(o.url);
    const contact = o.contact || o.extra?.contact || "";
    const id = esc(o.uid).replace(/[^a-zA-Z0-9_-]/g, "_");
    const gone = o.active === false;
    const why = o.why ? `<p class="why">${esc(o.why)}</p>` : "";
    const reasons = (o.reasons || []).length ? `<div class="reasons">Correspond :${o.reasons.map(r => `<span class="tag">${esc(r)}</span>`).join("")}</div>` : "";
    const also = (o.also_on || []).filter(a => safeUrl(a.url)).map(a => `<a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.source)}</a>`).join(" · ");
    // Inclinaison et nuance stables pour chaque post-it (dérivées de l'identifiant)
    let h = 0; for (const ch of o.uid) h = (h * 31 + ch.charCodeAt(0)) | 0;
    const rot = ((Math.abs(h) % 7) - 3) * 0.55;
    const stamp = st !== STATUSES[0] ? `<span class="stamp st-${STATUSES.indexOf(st)}" aria-hidden="true">${esc(st)}</span>` : "";
    return `<article class="job cat-${esc(o.category || "autre")} ${o.mine || o.source === "manuel" ? "pinned" : ""} ${HIDDEN.has(st) || gone ? "dim" : ""}" style="--rot:${rot}deg" data-uid="${esc(o.uid)}">
      ${stamp}
      <div class="head"><span class="org">${esc(o.org || "Organisme non précisé")}</span><h3 class="title">${esc(o.title)}</h3></div>
      <div class="badges">
        ${isNew(o) ? `<span class="pill new">Nouvelle</span>` : ""}
        ${o.mine ? `<span class="pill mine">Ajoutée</span>` : ""}
        ${gone ? `<span class="pill lo">${o.archived ? "Archivée" : "Plus en ligne"}</span>` : ""}
        ${deadlineBadge(o)}
        <span class="pill ${esc(o.fit)}">${FIT[o.fit] || ""}${o.score != null && o.source !== "manuel" && !o.mine ? ` · <span class="score">${o.score}</span>` : ""}</span>
      </div>
      <div class="meta">
        ${o.location ? `<span>${esc(o.location)}</span>` : ""}
        ${o.contract ? `<span>${esc(o.contract)}</span>` : ""}
        ${o.salary ? `<span>${esc(o.salary)}</span>` : ""}
        ${o.deadline ? `<span class="mono">Date limite ${fmtDate(o.deadline)}</span>` : ""}
        ${o.published ? `<span class="mono">Publiée le ${fmtDate(o.published)}</span>` : ""}
        ${gone && o.last_seen ? `<span class="mono">Vue pour la dernière fois le ${fmtDate(o.last_seen)}</span>` : ""}
      </div>
      ${why}${reasons}
      ${contact ? `<div class="contact">Contact : <span class="mono">${esc(contact)}</span><button class="link-btn" type="button" data-copy="${esc(contact)}">Copier</button></div>` : ""}
      ${o.description ? `<details class="more"><summary>Résumé de l'annonce</summary><p>${esc(o.description)}</p></details>` : ""}
      <details class="more" ${notes ? "open" : ""}><summary>Mes notes</summary>
        <textarea id="notes-${id}" data-notes="${esc(o.uid)}" rows="3" placeholder="Relances, interlocuteurs, prochaines étapes…">${esc(notes)}</textarea>
      </details>
      <div class="foot">
        <div class="links">
          ${url ? `<a class="main" href="${esc(url)}" target="_blank" rel="noopener">Voir l'offre ↗</a>` : ""}
          <span class="mono">${esc(o.source_label || (o.mine ? "Ajoutée à la main" : ""))}${o.via ? ` via ${esc(o.via)}` : ""}</span>
          ${also ? `<span>Aussi sur : ${also}</span>` : ""}
        </div>
        <div class="right">
          ${o.mine ? `<button class="btn small danger" type="button" data-del="${esc(o.uid)}">Supprimer</button>` : ""}
          <label>Statut <select id="status-${id}" data-status="${esc(o.uid)}">${STATUSES.map(s => `<option${s === st ? " selected" : ""}>${s}</option>`).join("")}</select></label>
        </div>
      </div>
    </article>`;
  }

  function renderList() {
    const list = filtered();
    const page = list.slice(0, S.shown);
    $("#count").textContent = list.length ? `${list.length} offre${list.length > 1 ? "s" : ""}${list.length > page.length ? `, ${page.length} affichées` : ""}` : "";
    $("#list").innerHTML = page.length ? page.map(card).join("") : `<div class="empty">Aucune offre ne correspond à ces filtres.</div>`;
    $("#btn-more").hidden = list.length <= S.shown;
  }

  // ------------------------------------------------------------------ rendu : autres onglets
  function renderEcheances() {
    const items = [...(S.meta.echeances || [])].sort((a, b) => (a.date || "9999").localeCompare(b.date || "9999"));
    const upcoming = items.filter(e => e.date && daysFrom(e.date) >= 0).length;
    $("#n-echeances").textContent = upcoming || "";
    $("#echeances").innerHTML = items.length ? items.map(e => {
      const n = daysFrom(e.date);
      const when = e.date ? `${fmtDate(e.date)}<small>${n < 0 ? "passée" : n === 0 ? "aujourd'hui" : "dans " + n + " j"}</small>` : `À confirmer<small>date non fixée</small>`;
      const url = safeUrl(e.url);
      return `<li class="${n !== null && n < 0 ? "past" : ""}">
        <div class="when ${n !== null && n >= 0 && n <= 21 ? "soon" : ""}">${when}</div>
        <div><h3>${esc(e.title)}</h3>${e.detail ? `<p>${esc(e.detail)}</p>` : ""}${url ? `<p><a href="${esc(url)}" target="_blank" rel="noopener">Site officiel ↗</a></p>` : ""}</div>
      </li>`;
    }).join("") : `<div class="empty">Aucune échéance dans ce profil.</div>`;
  }

  function renderLiens() {
    const groups = S.meta.liens || [];
    $("#liens").innerHTML = groups.length ? groups.map(g => `<section class="link-group"><h2>${esc(g.groupe)}</h2><ul>${
      (g.sites || []).filter(s => safeUrl(s.url)).map(s => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.nom)} ↗</a></li>`).join("")
    }</ul></section>`).join("") : `<div class="empty">Aucun lien rapide dans ce profil.</div>`;
  }

  function renderSources() {
    const st = S.status;
    if (!st || !st.sources?.length) {
      $("#sources-intro").textContent = "Le collecteur n'a pas encore tourné. Lance le workflow « Collecte des offres » depuis l'onglet Actions du dépôt.";
      $("#sources").innerHTML = ""; $("#n-sources").textContent = ""; return;
    }
    const bad = st.sources.filter(s => ["error", "blocked"].includes(s.state)).length;
    $("#n-sources").textContent = bad ? `⚠ ${bad}` : "";
    $("#sources-intro").textContent = `Dernier passage : ${new Date(st.generated).toLocaleString("fr-FR", { dateStyle: "long", timeStyle: "short" })} · ${st.raw} offres brutes, ${st.unique} après dédoublonnage (tous profils confondus).`;
    $("#sources").innerHTML = `<thead><tr><th>Source</th><th>État</th><th>Offres</th><th>Détail</th></tr></thead><tbody>${st.sources.map(s => {
      const [label, cls] = STATE_LABEL[s.state] || [s.state, "lo"];
      const warn = (s.warnings || []).length ? `<ul>${s.warnings.map(w => `<li>${esc(w)}</li>`).join("")}</ul>` : "";
      const name = safeUrl(s.homepage) ? `<a href="${esc(s.homepage)}" target="_blank" rel="noopener">${esc(s.label)}</a>` : esc(s.label);
      return `<tr><td>${name}</td><td><span class="pill ${cls}">${label}</span></td><td class="num">${s.count ?? 0}</td><td>${esc(s.message || "")}${warn}</td></tr>`;
    }).join("")}</tbody>`;
  }

  function renderAll() { renderStats(); renderFilters(); renderList(); renderEcheances(); renderLiens(); renderSources(); }

  // ------------------------------------------------------------------ suivi
  function snapshot(uid) {
    const o = allOffers().find(x => x.uid === uid);
    if (!o) return S.track[uid]?.snapshot;
    const { uid: _, active, archived, mine, ...rest } = o;
    return { ...rest, description: (rest.description || "").slice(0, 300) };
  }
  function setTrack(uid, patch) {
    S.track[uid] = { ...S.track[uid], ...patch, snapshot: snapshot(uid), updated: new Date().toISOString() };
    store.set(key("track"), S.track);
  }

  // ------------------------------------------------------------------ événements
  function switchTab(tab) {
    S.tab = tab;
    document.querySelectorAll(".tab").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === tab));
    document.querySelectorAll(".panel").forEach(p => (p.hidden = p.id !== `panel-${tab}`));
    if (location.hash.slice(1) !== tab) history.replaceState(null, "", tab === "offres" ? location.pathname + location.search : `#${tab}`);
  }
  document.querySelector(".tabs").addEventListener("click", e => { const b = e.target.closest("[data-tab]"); if (b) switchTab(b.dataset.tab); });
  window.addEventListener("hashchange", () => switchTab(["echeances", "liens", "sources"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "offres"));

  $("#profile").addEventListener("change", async e => {
    S.profile = e.target.value;
    const u = new URL(location.href); u.searchParams.set("p", S.profile); history.replaceState(null, "", u);
    await loadProfile();
  });
  $("#chips").addEventListener("click", e => { const b = e.target.closest("[data-cat]"); if (!b) return; S.f.cat = b.dataset.cat; S.shown = PAGE; renderFilters(); renderList(); });
  const bind = (sel, prop, ev = "change", get = el => el.value) => $(sel).addEventListener(ev, e => { S.f[prop] = get(e.target); S.shown = PAGE; renderList(); });
  bind("#q", "q", "input");
  bind("#sort", "sort");
  bind("#f-source", "source");
  bind("#f-new", "onlyNew", "change", el => el.checked);
  bind("#f-idf", "idf", "change", el => el.checked);
  bind("#f-hide", "hide", "change", el => el.checked);
  bind("#f-gone", "gone", "change", el => el.checked);
  $("#f-status").innerHTML = `<option value="">Tous</option>` + STATUSES.map(s => `<option>${s}</option>`).join("");
  bind("#f-status", "status");
  $("#btn-more").addEventListener("click", () => { S.shown += PAGE; renderList(); });

  $("#list").addEventListener("change", e => {
    const uid = e.target.dataset.status;
    if (uid) { setTrack(uid, { status: e.target.value }); renderStats(); renderList(); toast(`Statut : ${e.target.value}`); }
  });
  $("#list").addEventListener("input", e => {
    const uid = e.target.dataset.notes;
    if (uid) { clearTimeout(setTrack.t); const v = e.target.value; setTrack.t = setTimeout(() => setTrack(uid, { notes: v }), 400); }
  });
  $("#list").addEventListener("click", async e => {
    const c = e.target.closest("[data-copy]");
    if (c) {
      try { await navigator.clipboard.writeText(c.dataset.copy); toast("Adresse copiée"); }
      catch { const r = document.createRange(); r.selectNodeContents(c.previousElementSibling); getSelection().removeAllRanges(); getSelection().addRange(r); toast("Adresse sélectionnée : Ctrl+C"); }
      return;
    }
    const d = e.target.closest("[data-del]");
    if (!d) return;
    if (d.dataset.armed) {
      S.custom = S.custom.filter(o => o.uid !== d.dataset.del); delete S.track[d.dataset.del];
      store.set(key("custom"), S.custom); store.set(key("track"), S.track); renderAll(); toast("Offre supprimée");
    } else {
      d.dataset.armed = "1"; d.textContent = "Confirmer la suppression";
      setTimeout(() => { if (d.isConnected) { delete d.dataset.armed; d.textContent = "Supprimer"; } }, 3000);
    }
  });

  // Ajout manuel
  const dlg = $("#dlg");
  $("#btn-add").addEventListener("click", () => { $("#form").reset(); dlg.showModal(); $("#i-title").focus(); });
  $("#btn-cancel").addEventListener("click", () => dlg.close());
  $("#form").addEventListener("submit", e => {
    e.preventDefault();
    const v = s => $(s).value.trim();
    const slug = (v("#i-org") + "-" + v("#i-title")).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").slice(0, 40);
    const id = `${slug}-${Date.now().toString(36)}`;
    S.custom.push({
      uid: `perso:${id}`, id, source: "perso", source_label: "Ajoutée à la main",
      category: v("#i-category"), fit: v("#i-fit"), title: v("#i-title"), org: v("#i-org"), location: v("#i-location"),
      contract: v("#i-contract"), deadline: v("#i-deadline") || null, published: new Date().toISOString().slice(0, 10),
      why: v("#i-why"), contact: v("#i-contact"), url: v("#i-url"), active: true,
    });
    store.set(key("custom"), S.custom); dlg.close(); renderAll(); toast("Offre ajoutée");
  });

  // Export / import
  function download(name, text, type) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }
  $("#btn-export").addEventListener("click", () => {
    download(`suivi-${S.profile}-${new Date().toISOString().slice(0, 10)}.json`,
      JSON.stringify({ version: 2, profile: S.profile, exported: new Date().toISOString(), track: S.track, custom: S.custom }, null, 1), "application/json");
    toast("Suivi exporté");
  });
  $("#file-import").addEventListener("change", async e => {
    const f = e.target.files[0]; if (!f) return;
    try {
      const data = JSON.parse(await f.text());
      if (typeof data.track !== "object" || !Array.isArray(data.custom)) throw new Error();
      if (data.profile && data.profile !== S.profile) toast(`Attention : export du profil « ${data.profile} »`);
      S.track = { ...S.track, ...data.track };
      const ids = new Set(S.custom.map(o => o.uid));
      S.custom = [...S.custom, ...data.custom.filter(o => o && o.uid && !ids.has(o.uid))];
      store.set(key("track"), S.track); store.set(key("custom"), S.custom); renderAll(); toast("Suivi importé");
    } catch { toast("Fichier non reconnu : choisis un export de cette application"); }
    e.target.value = "";
  });
  $("#btn-manual").addEventListener("click", () => {
    const fromFeed = S.offers.filter(o => o.source === "manuel").map(o => ({
      id: o.source_id, category: o.category, fit: o.fit, org: o.org, title: o.title, location: o.location, contract: o.contract,
      deadline: o.deadline, published: o.published, why: o.why, contact: o.extra?.contact || "", url: o.url,
    }));
    const added = S.custom.map(o => ({ id: o.id, category: o.category, fit: o.fit, org: o.org, title: o.title, location: o.location,
      contract: o.contract, deadline: o.deadline, published: o.published, why: o.why, contact: o.contact, url: o.url }));
    download("manual.json", JSON.stringify([...fromFeed, ...added], null, 1) + "\n", "application/json");
    toast(`manual.json : à placer dans profiles/${S.profile}/`);
  });

  // Thème
  const applyTheme = t => { if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme; };
  applyTheme(store.get("suivi:theme", null));
  $("#btn-theme").addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark"; applyTheme(next); store.set("suivi:theme", next);
  });

  if (["echeances", "liens", "sources"].includes(location.hash.slice(1))) switchTab(location.hash.slice(1));
  boot();
})();
