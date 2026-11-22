/* Carte « Visiteurs » — module Visiteurs (Basilik41/hass-visiteurs).
 *   type: custom:visiteurs-card
 *   mode: auto | gestion | accueil     (auto : tablette murale → accueil ; sinon gestion)
 *   title: Visiteurs
 */
/* global __QR__ */
const VERSION = "1.1.0";
const QR = __QR__;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pad = (n) => String(n).padStart(2, "0");
const TYPES = { sur_place: "Reste sur place", passage: "Passage" };
const JOURS = ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."];

function qrSvg(text) {
  if (!text) return "";
  try {
    const q = QR(0, "M");
    q.addData(text, "Byte");
    q.make();
    return q.createSvgTag({ cellSize: 4, margin: 2, scalable: true });
  } catch (e) {
    return "";
  }
}

// « 2026-11-22T14:30 » (heure locale du navigateur) pour <input type=datetime-local>
function toLocalInput(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function fromLocalInput(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(s || "");
  return m ? new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]) : null;
}
// envoyé au serveur : heure locale sans fuseau (le serveur applique le fuseau de Home Assistant)
const toServer = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:00`;

function quand(iso, now = new Date()) {
  const d = new Date(iso);
  if (isNaN(d)) return "?";
  const h = `${d.getHours()} h${d.getMinutes() ? " " + pad(d.getMinutes()) : ""}`;
  const days = Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 864e5);
  if (days === 0) return `aujourd'hui ${h}`;
  if (days === 1) return `demain ${h}`;
  if (days === -1) return `hier ${h}`;
  return `${JOURS[d.getDay()]} ${d.getDate()}/${pad(d.getMonth() + 1)} ${h}`;
}

function atHour(base, days, hour) {
  const d = new Date(base);
  d.setDate(d.getDate() + days);
  d.setHours(hour, 0, 0, 0);
  return d;
}

// choix rapides de départ selon le type (à partir de l'arrivée)
function quickEnds(type, start) {
  const plus = (h) => new Date(start.getTime() + h * 3600e3);
  const sameDay = (h) => { const d = atHour(start, 0, h); return d > start ? d : null; };
  if (type === "passage") {
    return [["1 h", plus(1)], ["2 h", plus(2)], ["4 h", plus(4)], ["Fin de journée", sameDay(19)], ["Demain 19 h", atHour(start, 1, 19)]]
      .filter(([, d]) => d);
  }
  return [["Ce soir", sameDay(23)], ["Demain matin", atHour(start, 1, 10)], ["2 jours", atHour(start, 2, 10)],
    ["1 semaine", atHour(start, 7, 10)]].filter(([, d]) => d);
}

const CSS = `
  :host { display:block; }
  ha-card { padding:16px; }
  .tete { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
  .tete h2 { flex:1; margin:0; font-size:1.25em; font-weight:500; }
  button { font:inherit; cursor:pointer; border-radius:10px; border:1px solid var(--divider-color,#ccc);
    background:var(--card-background-color,#fff); color:var(--primary-text-color); padding:8px 12px; min-height:40px; }
  button.p { background:var(--primary-color); color:var(--text-primary-color,#fff); border-color:transparent; }
  button.d { color:var(--error-color,#c62828); }
  button.d.sure { background:var(--error-color,#c62828); color:#fff; }
  button:disabled { opacity:.5; cursor:default; }
  h3 { margin:16px 0 6px; font-size:.85em; text-transform:uppercase; letter-spacing:.05em; color:var(--secondary-text-color); }
  .vide { color:var(--secondary-text-color); margin:8px 0; }
  .v { border:1px solid var(--divider-color,#ddd); border-radius:14px; padding:12px; margin:8px 0; }
  .v.en_cours { border-color:var(--success-color,#2e7d32); }
  .l1 { display:flex; align-items:center; gap:10px; }
  .av { width:40px; height:40px; border-radius:50%; display:flex; align-items:center; justify-content:center; flex:none;
    background:var(--primary-color); color:var(--text-primary-color,#fff); font-weight:600; font-size:1.1em; }
  .v.passage .av { background:var(--info-color,#0288d1); }
  .v.terminee .av { background:var(--disabled-color,#9e9e9e); }
  .nom { font-weight:600; font-size:1.05em; }
  .sub { color:var(--secondary-text-color); font-size:.9em; }
  .tags { display:flex; flex-wrap:wrap; gap:6px; margin:8px 0 0; }
  .tag { font-size:.85em; padding:3px 8px; border-radius:999px; background:var(--secondary-background-color,#eee); }
  .tag.ok { background:rgba(46,125,50,.15); color:var(--success-color,#2e7d32); }
  .tag.code { font-family:monospace; letter-spacing:.15em; cursor:pointer; }
  .acts { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
  .acts button { min-height:36px; padding:6px 10px; font-size:.9em; }
  details summary { cursor:pointer; color:var(--secondary-text-color); margin-top:12px; }
  .err { color:var(--error-color,#c62828); margin:6px 0; }
  .accueil { text-align:center; }
  .accueil .bienv { font-size:1.5em; font-weight:500; margin:6px 0 12px; }
  .wifi { display:flex; gap:16px; align-items:center; justify-content:center; flex-wrap:wrap; margin:8px 0; }
  .qr { width:180px; height:180px; background:#fff; padding:6px; border-radius:12px; }
  .qr svg { width:100%; height:100%; display:block; }
  .wtxt { text-align:left; }
  .wtxt b { font-size:1.15em; }
  .mdp { font-family:monospace; font-size:1.15em; user-select:all; }
  .consignes { white-space:pre-wrap; text-align:left; background:var(--secondary-background-color,#f5f5f5); border-radius:12px; padding:12px; margin-top:12px; }
  /* formulaire */
  .fond { position:fixed; inset:0; background:rgba(0,0,0,.45); z-index:9; display:flex; align-items:flex-end; justify-content:center; }
  @media (min-width:600px) { .fond { align-items:center; } }
  .boite { background:var(--card-background-color,#fff); color:var(--primary-text-color); width:min(560px,100%); max-height:92vh; overflow:auto;
    border-radius:18px 18px 0 0; padding:18px; box-sizing:border-box; }
  @media (min-width:600px) { .boite { border-radius:18px; } }
  .boite h2 { margin:0 0 10px; font-size:1.2em; }
  label.c { display:block; font-size:.85em; color:var(--secondary-text-color); margin:12px 0 4px; }
  input[type=text], input[type=tel], input[type=datetime-local], textarea { width:100%; box-sizing:border-box; font:inherit;
    padding:10px; border-radius:10px; border:1px solid var(--divider-color,#ccc); background:var(--card-background-color,#fff); color:inherit; }
  textarea { min-height:70px; }
  .seg { display:flex; gap:6px; flex-wrap:wrap; }
  .seg button { flex:1; min-width:fit-content; }
  .seg button.on { background:var(--primary-color); color:var(--text-primary-color,#fff); border-color:transparent; }
  .chips { display:flex; flex-wrap:wrap; gap:6px; }
  .chips button { min-height:34px; padding:4px 10px; font-size:.9em; }
  .chips button.on { background:var(--primary-color); color:var(--text-primary-color,#fff); border-color:transparent; }
  .res { font-size:.9em; color:var(--secondary-text-color); margin-top:6px; }
  .chk { display:flex; align-items:center; gap:8px; margin:6px 0; min-height:36px; }
  .chk input { width:20px; height:20px; }
  .warn { color:var(--warning-color,#ef6c00); font-size:.85em; }
  .pied { display:flex; justify-content:flex-end; gap:8px; margin-top:16px; position:sticky; bottom:-18px; background:inherit; padding:8px 0; }
  .grandcode { font-family:monospace; font-size:2em; letter-spacing:.3em; text-align:center; margin:8px 0; }
`;

class VisiteursCard extends HTMLElement {
  setConfig(config) {
    this.config = { mode: "auto", title: "Visiteurs", ...config };
    if (!["auto", "gestion", "accueil"].includes(this.config.mode)) throw new Error("mode : auto, gestion ou accueil");
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.info = null; this.form = null; this.result = null; this.sure = null; this.reveal = new Set();
    this._render();
  }

  getCardSize() { return 4; }
  static getStubConfig() { return { title: "Visiteurs" }; }

  set hass(h) {
    const first = !this._hass;
    this._hass = h;
    if (first) { this._load(); return; }
    // rechargé quand une entité du module change (début, fin, arrivée…)
    const sig = Object.keys(h.states).filter((e) => /^(sensor|binary_sensor)\..*visit/.test(e))
      .map((e) => h.states[e].last_updated).join("|");
    if (sig !== this._sig) { const had = this._sig !== undefined; this._sig = sig; if (had && !this.reg && !this.form) this._load(); }
  }

  connectedCallback() {
    clearInterval(this._timer);
    this._timer = setInterval(() => { if (!this.form && !this.reg) this._load(); }, 60000);
  }
  disconnectedCallback() { clearInterval(this._timer); }

  get tablet() { return /tabdomo/i.test(this._hass?.user?.name || ""); }
  get mode() {
    if (this.config.mode !== "auto") return this.config.mode;
    return this.tablet || (this.info && !this.info.gestion) ? "accueil" : "gestion";
  }

  async _ws(msg) { return this._hass.callWS(msg); }

  async _load() {
    if (!this._hass) return;
    try {
      this.info = await this._ws({ type: "visiteurs/info" });
      this._err = null;
    } catch (e) {
      this._err = e?.code === "unknown_command" ? "Module « Visiteurs » non installé." : (e?.message || String(e));
    }
    this._render();
  }

  _toast(msg) {
    this.dispatchEvent(new CustomEvent("hass-notification", { detail: { message: msg }, bubbles: true, composed: true }));
  }

  // ───────── affichage ─────────
  _render() {
    if (!this.shadowRoot) return;
    let body;
    if (this._err) body = `<p class="err">${esc(this._err)}</p>`;
    else if (!this.info) body = `<p class="vide">Chargement…</p>`;
    else body = this.mode === "accueil" ? this._accueil() : this._gestion();
    this.shadowRoot.innerHTML = `<style>${CSS}</style><ha-card>${body}</ha-card>${this.form ? this._formHtml() : ""}${this.result ? this._resultHtml() : ""}${this.reg ? this._regHtml() : ""}`;
    this._bind();
  }

  _accueil() {
    const i = this.info;
    const cur = i.visites.filter((v) => v.statut === "en_cours");
    const noms = cur.map((v) => v.nom);
    const w = i.wifi || {};
    const qr = w.qr ? qrSvg(w.qr) : "";
    const bienv = noms.length ? `Bienvenue ${esc(noms.length > 1 ? noms.slice(0, -1).join(", ") + " et " + noms.at(-1) : noms[0])} !` : esc(this.config.title_accueil || "Bienvenue !");
    return `<div class="accueil">
      <div class="bienv">${bienv}</div>
      ${w.ssid ? `<div class="wifi">${qr ? `<div class="qr" aria-label="QR code du Wi-Fi">${qr}</div>` : ""}
        <div class="wtxt"><div>📶 Wi-Fi</div><b>${esc(w.ssid)}</b>${w.mot_de_passe ? `<div class="sub">Mot de passe</div><div class="mdp">${esc(w.mot_de_passe)}</div>` : ""}
        <div class="sub" style="margin-top:6px">Scannez le QR code avec l'appareil photo.</div></div></div>`
        : (i.gestion ? `<p class="vide">Wi-Fi invité non réglé (options du module Visiteurs).</p>` : "")}
      ${i.consignes ? `<div class="consignes">${esc(i.consignes)}</div>` : ""}
    </div>`;
  }

  _gestion() {
    const i = this.info;
    const by = (s) => i.visites.filter((v) => v.statut === s);
    const cur = by("en_cours"), next = by("prevue"), done = by("terminee");
    return `<div class="tete"><h2>${esc(this.config.title)}</h2>
        ${i.admin ? `<button data-a="reglages" aria-label="Réglages des visiteurs" title="Réglages">⚙️</button>` : ""}
        ${i.gestion ? `<button class="p" data-a="nouveau">＋ Visiteur</button>` : ""}</div>
      ${cur.length ? `<h3>En ce moment</h3>${cur.map((v) => this._item(v)).join("")}` : `<p class="vide">Aucun visiteur en ce moment.</p>`}
      ${next.length ? `<h3>À venir</h3>${next.map((v) => this._item(v)).join("")}` : ""}
      ${done.length ? `<details ${this._open ? "open" : ""}><summary>Terminées (${done.length})</summary>${done.map((v) => this._item(v)).join("")}</details>` : ""}`;
  }

  _item(v) {
    const i = this.info, g = i.gestion;
    let when;
    if (v.statut === "en_cours") when = `jusqu'à ${quand(v.fin)}`;
    else if (v.statut === "prevue") when = `arrive ${quand(v.debut)} · jusqu'à ${quand(v.fin)}`;
    else when = `${quand(v.debut)} → ${quand(v.fin)}`;
    const tags = [];
    tags.push(`<span class="tag">${esc(TYPES[v.type] || v.type)}</span>`);
    if (v.arrivee) tags.push(`<span class="tag ok">✓ arrivé·e ${esc(quand(v.arrivee.t))}</span>`);
    (v.plaques || []).forEach((p) => tags.push(`<span class="tag">🚗 ${esc(p)}</span>`));
    if (v.a_un_code && g && v.code) {
      const show = this.reveal.has(v.id);
      tags.push(`<span class="tag code" data-a="voir" data-id="${esc(v.id)}" role="button" aria-label="${show ? "Masquer" : "Afficher"} le code">🔑 ${show ? esc(v.code) : "••••••"}</span>`);
    } else if (v.a_un_code) tags.push(`<span class="tag">🔑 code</span>`);
    if (v.acces?.length) {
      const names = Object.fromEntries((i.acces || []).map((a) => [a.entity_id, a.nom]));
      tags.push(`<span class="tag">ouvre : ${esc(v.acces.map((e) => names[e] || e).join(", "))}</span>`);
    }
    if (v.note) tags.push(`<span class="tag">📝 ${esc(v.note)}</span>`);
    const sure = (k) => this.sure === `${k}:${v.id}`;
    const acts = !g ? "" : `<div class="acts">
      ${v.statut !== "terminee" ? `<button data-a="message" data-id="${esc(v.id)}">✉️ Message</button>` : ""}
      ${v.statut === "en_cours" ? `<button data-a="plus" data-id="${esc(v.id)}">＋2 h</button>` : ""}
      <button data-a="modifier" data-id="${esc(v.id)}">${v.statut === "terminee" ? "Revenir" : "Modifier"}</button>
      ${v.statut === "en_cours" ? `<button class="d ${sure("terminer") ? "sure" : ""}" data-a="terminer" data-id="${esc(v.id)}">${sure("terminer") ? "Confirmer le départ" : "Parti·e"}</button>` : ""}
      ${v.statut !== "en_cours" ? `<button class="d ${sure("supprimer") ? "sure" : ""}" data-a="supprimer" data-id="${esc(v.id)}">${sure("supprimer") ? "Confirmer" : "Supprimer"}</button>` : ""}
    </div>`;
    return `<div class="v ${esc(v.statut)} ${esc(v.type)}"><div class="l1"><div class="av">${esc((v.nom || "?").slice(0, 1).toUpperCase())}</div>
      <div><div class="nom">${esc(v.nom)}</div><div class="sub">${esc(when)}</div></div></div>
      <div class="tags">${tags.join("")}</div>${acts}</div>`;
  }

  // ───────── formulaire ─────────
  _newForm(v) {
    const now = new Date();
    if (!v) {
      return { id: null, nom: "", type: "sur_place", maintenant: true, debut: toLocalInput(new Date(now.getTime() + 3600e3)),
        fin: null, choix: null, plaques: "", telephone: "", note: "", code: false, acces: [], alarme: false, err: "", busy: false, statut: "nouvelle" };
    }
    return { id: v.id, nom: v.nom, type: v.type, maintenant: false, debut: toLocalInput(new Date(v.debut)),
      fin: toLocalInput(new Date(v.statut === "terminee" ? Math.max(Date.now() + 2 * 3600e3, new Date(v.fin)) : new Date(v.fin))),
      choix: "autre", plaques: (v.plaques || []).join(", "), telephone: v.telephone || "", note: v.note || "",
      code: !!v.a_un_code, codeMode: "garder", acces: [...(v.acces || [])], alarme: !!v.alarme, err: "", busy: false, statut: v.statut };
  }

  _start(f) { return f.maintenant ? new Date() : fromLocalInput(f.debut); }

  _formHtml() {
    const f = this.form, i = this.info;
    const start = this._start(f) || new Date();
    const quick = quickEnds(f.type, start);
    const fin = f.choix === "autre" ? fromLocalInput(f.fin) : (quick.find(([k]) => k === f.choix)?.[1] || null);
    const started = f.statut === "en_cours";
    const acc = i.acces || [];
    const alarmChecked = f.acces.some((e) => e.startsWith("alarm_control_panel."));
    return `<div class="fond"><div class="boite" role="dialog" aria-modal="true" aria-labelledby="ft">
      <h2 id="ft">${f.id ? `Modifier — ${esc(f.nom)}` : "Nouveau visiteur"}</h2>
      ${f.err ? `<p class="err" role="alert">${esc(f.err)}</p>` : ""}
      <label class="c" for="nom">Nom</label><input id="nom" type="text" maxlength="60" autocomplete="off" value="${esc(f.nom)}" placeholder="Prénom ou nom">
      <label class="c">Type</label><div class="seg">
        <button data-f="type" data-v="sur_place" class="${f.type === "sur_place" ? "on" : ""}">🛏️ Reste sur place</button>
        <button data-f="type" data-v="passage" class="${f.type === "passage" ? "on" : ""}">🔧 Passage</button></div>
      <div class="res">${f.type === "sur_place" ? "Compte comme quelqu'un à la maison : pas d'extinction ni de mode absence, pas d'armement automatique." : "Artisan, livreur, voisin… : les caméras le signalent en simple info (sauf la nuit)."}</div>
      ${started ? "" : `<label class="c">Arrivée</label><div class="seg">
        <button data-f="maintenant" data-v="1" class="${f.maintenant ? "on" : ""}">Là maintenant</button>
        <button data-f="maintenant" data-v="0" class="${!f.maintenant ? "on" : ""}">Plus tard</button></div>
        ${f.maintenant ? "" : `<input id="debut" type="datetime-local" value="${esc(f.debut)}" style="margin-top:6px">`}`}
      <label class="c">Départ</label><div class="chips">
        ${quick.map(([k]) => `<button data-f="choix" data-v="${esc(k)}" class="${f.choix === k ? "on" : ""}">${esc(k)}</button>`).join("")}
        <button data-f="choix" data-v="autre" class="${f.choix === "autre" ? "on" : ""}">Autre…</button></div>
      ${f.choix === "autre" ? `<input id="fin" type="datetime-local" value="${esc(f.fin || toLocalInput(new Date(start.getTime() + 2 * 3600e3)))}" style="margin-top:6px">` : ""}
      <div class="res">${fin ? `Jusqu'à ${esc(quand(fin.toISOString()))}` : (f.id ? "" : `Sans choix : ${esc(String(f.type === "passage" ? i.durees?.passage : i.durees?.sur_place))} h`)}</div>
      <label class="c" for="plaques">Véhicule (plaque, facultatif)</label><input id="plaques" type="text" maxlength="60" value="${esc(f.plaques)}" placeholder="AB-123-CD" autocapitalize="characters">
      <label class="c" for="tel">Téléphone (pour lui envoyer le message)</label><input id="tel" type="tel" maxlength="30" value="${esc(f.telephone)}">
      ${acc.length ? `<label class="chk"><input type="checkbox" id="code" ${f.code ? "checked" : ""}> Donner un code visiteur (tablette)</label>
        ${f.code ? `<div style="margin-left:8px">${acc.map((a) => `<label class="chk"><input type="checkbox" data-acc="${esc(a.entity_id)}" ${f.acces.includes(a.entity_id) ? "checked" : ""}> ${esc(a.nom)}${a.alarme ? " (alarme)" : ""}</label>`).join("")}
          ${alarmChecked ? `<label class="chk"><input type="checkbox" id="alarme" ${f.alarme ? "checked" : ""}> Peut désarmer l'alarme</label><div class="warn">Sans cette case, le code ne désarme jamais l'alarme.</div>` : ""}
          ${f.id && f.codeMode !== undefined && this._wasCoded ? `<label class="chk"><input type="checkbox" id="nouveaucode" ${f.codeMode === "nouveau" ? "checked" : ""}> Changer le code</label>` : ""}
          <div class="res">Le code ne marche que pendant la visite, sur les tablettes, et vous prévient à chaque usage.</div></div>` : ""}`
        : ""}
      <label class="c" for="note">Note</label><textarea id="note" maxlength="500">${esc(f.note)}</textarea>
      <div class="pied"><button data-a="annuler">Annuler</button><button class="p" data-a="enregistrer" ${f.busy ? "disabled" : ""}>Enregistrer</button></div>
    </div></div>`;
  }

  // ───────── réglages (administrateurs) ─────────
  _regHtml() {
    const r = this.reg, v = r.v;
    if (!r.data) return `<div class="fond"><div class="boite"><p>Chargement…</p></div></div>`;
    const d = r.data;
    const num = (k, lab, unit, min, max, step) => `<label class="c" for="r_${k}">${lab}</label>
      <div style="display:flex;align-items:center;gap:8px"><input id="r_${k}" data-r="${k}" type="number" min="${min}" max="${max}" step="${step}" value="${esc(v[k])}" style="width:110px;padding:10px;border-radius:10px;border:1px solid var(--divider-color,#ccc);font:inherit;background:var(--card-background-color,#fff);color:inherit"> ${unit}</div>`;
    const sel = (k, opts) => `<div class="seg">${opts.map(([val, lab]) => `<button data-rs="${k}" data-v="${esc(val)}" class="${String(v[k]) === String(val) ? "on" : ""}">${esc(lab)}</button>`).join("")}</div>`;
    const timeIn = (k) => `<input data-r="${k}" type="time" value="${esc(String(v[k] || "").slice(0, 5))}" style="padding:10px;border-radius:10px;border:1px solid var(--divider-color,#ccc);font:inherit;background:var(--card-background-color,#fff);color:inherit">`;
    return `<div class="fond"><div class="boite" role="dialog" aria-modal="true" aria-labelledby="rgt">
      <h2 id="rgt">Réglages des visiteurs — ${esc(this.info.site || "")}</h2>
      ${r.err ? `<p class="err" role="alert">${esc(r.err)}</p>` : ""}
      <h3>Wi-Fi invité</h3>
      <label class="c" for="r_ssid">Nom du réseau</label><input id="r_ssid" data-r="wifi_ssid" type="text" maxlength="32" value="${esc(v.wifi_ssid || "")}" placeholder="ex. Les Roches Invités">
      <label class="c" for="r_mdp">Mot de passe</label>
      <div style="display:flex;gap:6px"><input id="r_mdp" data-r="wifi_mot_de_passe" type="text" maxlength="63" value="${esc(v.wifi_mot_de_passe || "")}" autocomplete="off" spellcheck="false" style="flex:1"><button data-a="r_gen">🎲 Générer</button></div>
      <label class="c">Sécurité</label>${sel("wifi_securite", [["WPA", "WPA2"], ["SAE", "WPA3"], ["nopass", "Ouvert"]])}
      <div class="res">Le réseau se crée dans UniFi avec ce nom et ce mot de passe. Ici, ils servent au QR code de la tablette et au message d'accueil.</div>
      <h3>Accueil</h3>
      <label class="c" for="r_cons">Consignes</label><textarea id="r_cons" data-r="consignes" maxlength="2000" placeholder="ex. Fermer le portail derrière vous. Les chiens ne doivent pas sortir.">${esc(v.consignes || "")}</textarea>
      <label class="c" for="r_lum">Lumière d'accueil (allumée au début d'une visite s'il fait nuit)</label>
      <select id="r_lum" data-r="lumiere_accueil" style="width:100%;padding:10px;border-radius:10px;font:inherit;border:1px solid var(--divider-color,#ccc);background:var(--card-background-color,#fff);color:inherit">
        <option value="">Aucune</option>${d.lumieres_possibles.map((l) => `<option value="${esc(l.entity_id)}" ${v.lumiere_accueil === l.entity_id ? "selected" : ""}>${esc(l.nom)}</option>`).join("")}</select>
      <h3>Accès qu'on peut donner avec un code visiteur</h3>
      <div class="res">Pour chaque visite, on coche ensuite seulement ceux qu'on veut.</div>
      ${d.acces_possibles.map((a) => `<label class="chk"><input type="checkbox" data-racc="${esc(a.entity_id)}" ${(v.acces_proposes || []).includes(a.entity_id) ? "checked" : ""}> ${esc(a.nom)}${a.alarme ? " (alarme)" : ""}</label>`).join("") || `<p class="vide">Aucune porte, serrure ou alarme trouvée.</p>`}
      <h3>Comportement pendant une visite</h3>
      ${Object.entries(d.regles).map(([k, lab]) => `<label class="chk"><input type="checkbox" data-rb="${k}" ${v[k] !== false ? "checked" : ""}> ${esc(lab)}</label>`).join("")}
      <label class="c">Nuit (de … à …)</label><div style="display:flex;gap:8px;align-items:center">${timeIn("nuit_debut")} → ${timeIn("nuit_fin")}</div>
      <h3>Durées</h3>
      ${num("duree_passage_h", "Passage, par défaut", "h", 0.25, 24, 0.25)}
      ${num("duree_sur_place_h", "Séjour sur place, par défaut", "h", 1, 720, 1)}
      ${num("marge_avant_min", "Marge avant l'arrivée prévue", "min", 0, 240, 5)}
      ${num("marge_apres_min", "Marge après le départ prévu", "min", 0, 240, 5)}
      <h3>Notifications</h3>
      <label class="c">Prévenir de</label>${sel("prevenir", [["tout", "Tout"], ["arrivee_depart", "Arrivées, codes, fins"], ["codes", "Codes seulement"], ["rien", "Rien"]])}
      <label class="c">Qui</label>${sel("niveau", [["alerte", "Richard et Julie"], ["admin", "Administrateurs"], ["info", "Discord seulement"]])}
      <div class="pied"><button data-a="r_annuler">Annuler</button><button class="p" data-a="r_enregistrer" ${r.busy ? "disabled" : ""}>Enregistrer</button></div>
    </div></div>`;
  }

  _readReg() {
    const R = this.shadowRoot, v = this.reg?.v;
    if (!v) return;
    R.querySelectorAll("[data-r]").forEach((el) => { v[el.dataset.r] = el.type === "number" ? Number(el.value) : el.value; });
    R.querySelectorAll("[data-rb]").forEach((el) => { v[el.dataset.rb] = el.checked; });
    const acc = [];
    R.querySelectorAll("[data-racc]").forEach((el) => { if (el.checked) acc.push(el.dataset.racc); });
    if (R.querySelector("[data-racc]")) v.acces_proposes = acc;
  }

  async _openReg() {
    this.reg = { v: {}, data: null, err: "", busy: false };
    this._render();
    try {
      const r = await this._ws({ type: "visiteurs/reglages" });
      if (!r.ok) { this.reg = null; this._toast(r.message); return this._render(); }
      this.reg.data = r; this.reg.v = { ...r.valeurs };
    } catch (e) { this.reg = null; this._toast(e?.message || String(e)); }
    this._render();
  }

  async _saveReg(gen) {
    this._readReg();
    const v = this.reg.v;
    const msg = { type: "visiteurs/regler" };
    for (const [k, val] of Object.entries(v)) {
      if (val === null || val === undefined) continue;
      if (k === "nuit_debut" || k === "nuit_fin") { if (/^\d{2}:\d{2}/.test(val)) msg[k] = val.slice(0, 5) + ":00"; continue; }
      msg[k] = val;
    }
    if (gen) msg.wifi_generer = true;
    this.reg.busy = true; this.reg.err = ""; this._render();
    try {
      const r = await this._ws(msg);
      this.reg.busy = false;
      if (!r.ok) { this.reg.err = r.message; return this._render(); }
      if (gen) { this.reg.data = r; this.reg.v.wifi_mot_de_passe = r.valeurs.wifi_mot_de_passe; this._toast("Nouveau mot de passe enregistré"); }
      else { this.reg = null; this._toast("Réglages enregistrés"); }
      await this._load();
    } catch (e) { this.reg.busy = false; this.reg.err = e?.message || String(e); }
    this._render();
  }

  _resultHtml() {
    const r = this.result;
    const sms = r.telephone ? `sms:${encodeURIComponent(r.telephone.replace(/[^\d+]/g, ""))}?body=${encodeURIComponent(r.message)}` : "";
    return `<div class="fond"><div class="boite" role="dialog" aria-modal="true" aria-labelledby="rt">
      <h2 id="rt">${esc(r.titre)}</h2>
      ${r.code ? `<div class="sub" style="text-align:center">Code visiteur</div><div class="grandcode">${esc(r.code)}</div>` : ""}
      <label class="c" for="msg">Message à envoyer</label><textarea id="msg" readonly style="min-height:160px">${esc(r.message)}</textarea>
      <div class="pied"><button data-a="fermer">Fermer</button><button data-a="copier">Copier</button>
        ${navigator.share ? `<button data-a="partager">Partager</button>` : ""}
        ${sms ? `<a href="${esc(sms)}" style="text-decoration:none"><button class="p" type="button">SMS</button></a>` : ""}</div>
    </div></div>`;
  }

  _readForm() {
    const R = this.shadowRoot, f = this.form;
    if (!f) return;
    const val = (id) => R.getElementById(id)?.value;
    if (R.getElementById("nom")) f.nom = val("nom");
    if (R.getElementById("debut")) f.debut = val("debut");
    if (R.getElementById("fin")) f.fin = val("fin");
    if (R.getElementById("plaques")) f.plaques = val("plaques");
    if (R.getElementById("tel")) f.telephone = val("tel");
    if (R.getElementById("note")) f.note = val("note");
    if (R.getElementById("alarme")) f.alarme = R.getElementById("alarme").checked;
    if (R.getElementById("nouveaucode")) f.codeMode = R.getElementById("nouveaucode").checked ? "nouveau" : "garder";
  }

  _bind() {
    const R = this.shadowRoot;
    R.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", (e) => { e.stopPropagation(); this._act(b.dataset.a, b.dataset.id); }));
    R.querySelector("details")?.addEventListener("toggle", (e) => { this._open = e.target.open; });
    if (this.form) {
      R.querySelectorAll("[data-f]").forEach((b) => b.addEventListener("click", () => {
        this._readForm();
        const k = b.dataset.f, v = b.dataset.v;
        if (k === "maintenant") this.form.maintenant = v === "1";
        else if (k === "type") { this.form.type = v; if (this.form.choix !== "autre") this.form.choix = null; }
        else if (k === "choix") {
          this.form.choix = v;
          if (v === "autre" && !this.form.fin) this.form.fin = toLocalInput(new Date((this._start(this.form) || new Date()).getTime() + 2 * 3600e3));
        }
        this._render();
      }));
      R.getElementById("code")?.addEventListener("change", (e) => { this._readForm(); this.form.code = e.target.checked; this._render(); });
      R.querySelectorAll("[data-acc]").forEach((c) => c.addEventListener("change", () => {
        this._readForm();
        const id = c.dataset.acc;
        this.form.acces = c.checked ? [...new Set([...this.form.acces, id])] : this.form.acces.filter((x) => x !== id);
        if (!this.form.acces.some((x) => x.startsWith("alarm_control_panel."))) this.form.alarme = false;
        this._render();
      }));
      R.querySelector(".fond")?.addEventListener("click", (e) => { if (e.target.classList.contains("fond") && !this.form.busy) { this.form = null; this._render(); } });
      if (!this._focused) { R.getElementById("nom")?.focus(); this._focused = true; }
    }
    if (this.reg) {
      R.querySelectorAll("[data-rs]").forEach((b) => b.addEventListener("click", () => { this._readReg(); this.reg.v[b.dataset.rs] = b.dataset.v; this._render(); }));
    }
    if (this.result) R.querySelector(".fond")?.addEventListener("click", (e) => { if (e.target.classList.contains("fond")) { this.result = null; this._render(); } });
  }

  async _act(a, id) {
    const v = id ? this.info.visites.find((x) => x.id === id) : null;
    if (a !== "terminer" && a !== "supprimer") this.sure = null;
    switch (a) {
      case "reglages": return this._openReg();
      case "r_annuler": this.reg = null; break;
      case "r_enregistrer": return this._saveReg(false);
      case "r_gen": return this._saveReg(true);
      case "nouveau": this.form = this._newForm(null); this._wasCoded = false; this._focused = false; break;
      case "modifier": this.form = this._newForm(v); this._wasCoded = !!v?.a_un_code; this._focused = false; break;
      case "annuler": this.form = null; break;
      case "fermer": this.result = null; break;
      case "voir": this.reveal.has(id) ? this.reveal.delete(id) : this.reveal.add(id); break;
      case "enregistrer": return this._save();
      case "copier": return this._copy();
      case "partager":
        try { await navigator.share({ text: this.result.message }); } catch (e) { /* annulé */ }
        return;
      case "message": {
        const r = await this._call({ type: "visiteurs/message", visite: id });
        if (r) this.result = { titre: `Message pour ${v.nom}`, message: r.message, code: v.code, telephone: v.telephone };
        break;
      }
      case "plus": {
        const fin = new Date(Math.max(new Date(v.fin).getTime(), Date.now()) + 2 * 3600e3);
        if (await this._call({ type: "visiteurs/modifier", visite: id, fin: toServer(fin) })) this._toast(`${v.nom} : prolongé jusqu'à ${quand(fin.toISOString())}`);
        break;
      }
      case "terminer":
      case "supprimer":
        if (this.sure !== `${a}:${id}`) {
          this.sure = `${a}:${id}`;
          clearTimeout(this._sureT);
          this._sureT = setTimeout(() => { this.sure = null; this._render(); }, 4000);
          break;
        }
        this.sure = null;
        if (await this._call({ type: `visiteurs/${a}`, visite: id })) this._toast(a === "terminer" ? `Visite de ${v.nom} terminée` : "Visite supprimée");
        break;
      default: break;
    }
    this._render();
  }

  async _call(msg) {
    try {
      const r = await this._ws(msg);
      if (!r.ok) { this._toast(r.message || "Refusé"); return null; }
      await this._load();
      return r;
    } catch (e) {
      this._toast(e?.message || String(e));
      return null;
    }
  }

  async _copy() {
    const ta = this.shadowRoot.getElementById("msg");
    try { await navigator.clipboard.writeText(this.result.message); this._toast("Message copié"); }
    catch (e) { ta?.select(); try { document.execCommand("copy"); this._toast("Message copié"); } catch (e2) { this._toast("Copie impossible : sélectionner le texte"); } }
  }

  async _save() {
    this._readForm();
    const f = this.form, i = this.info;
    f.err = "";
    const nom = (f.nom || "").trim();
    if (!nom) { f.err = "Indiquer le nom du visiteur."; return this._render(); }
    const start = f.maintenant ? null : fromLocalInput(f.debut);
    if (!f.maintenant && f.statut !== "en_cours" && !start) { f.err = "Indiquer l'heure d'arrivée."; return this._render(); }
    const base = start || new Date();
    const quick = quickEnds(f.type, base);
    const fin = f.choix === "autre" ? fromLocalInput(f.fin) : (quick.find(([k]) => k === f.choix)?.[1] || null);
    if (f.choix === "autre" && !fin) { f.err = "Indiquer l'heure de départ."; return this._render(); }
    if (fin && fin <= base && f.statut !== "en_cours") { f.err = "Le départ doit être après l'arrivée."; return this._render(); }
    if (f.code && !f.acces.length) { f.err = "Cocher au moins un accès pour le code (ou décocher le code)."; return this._render(); }
    const msg = { type: f.id ? "visiteurs/modifier" : "visiteurs/ajouter", nom, type_visite: f.type, plaques: f.plaques,
      telephone: f.telephone, note: f.note, acces: f.code ? f.acces : [], alarme: f.code && f.alarme };
    if (f.id) msg.visite = f.id;
    if (f.statut !== "en_cours" && start) msg.debut = toServer(start); // « là maintenant » : le serveur prend l'heure actuelle
    if (fin) msg.fin = toServer(fin);
    if (!i.acces?.length) delete msg.acces;
    msg.code = f.code ? (f.id && this._wasCoded ? (f.codeMode || "garder") : "nouveau") : "aucun";
    if (!f.id && !f.code) msg.code = false;
    f.busy = true; this._render();
    try {
      const r = await this._ws(msg);
      f.busy = false;
      if (!r.ok) { f.err = r.message || "Refusé"; return this._render(); }
      this.form = null;
      await this._load();
      if (!f.id) {
        const v = r.visite;
        this.result = { titre: `${v.nom} : visite enregistrée`, message: r.message, code: v.code, telephone: v.telephone };
      } else this._toast("Visite modifiée");
    } catch (e) {
      f.busy = false; f.err = e?.message || String(e);
    }
    this._render();
  }
}

if (!customElements.get("visiteurs-card")) {
  customElements.define("visiteurs-card", VisiteursCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: "visiteurs-card", name: "Visiteurs", description: "Visites, codes visiteur et accueil (Wi-Fi)" });
  console.info(`%c VISITEURS-CARD %c ${VERSION} `, "background:#2e7d32;color:#fff", "");
}
