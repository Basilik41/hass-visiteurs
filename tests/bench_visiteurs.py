"""Banc de bout en bout sur un vrai Home Assistant (port 8123) : module Visiteurs + Codes d'accès 1.1.

Comptes : Richard (admin, personne), Julie (non admin, personne), « TabDomo Salon » (tablette), « Invité » (sans personne).
Usage : python bench_visiteurs.py [--restart-phase]
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timedelta

import aiohttp

BASE = "http://127.0.0.1:8123"
WS_URL = "ws://127.0.0.1:8123/api/websocket"
CLIENT = "http://127.0.0.1:8123/"
STATE_FILE = "/home/claude/banc/bench_state.json"
RESULTS: list[bool] = []


def check(name, cond, detail=""):
    RESULTS.append(bool(cond))
    print(("✅ " if cond else "❌ ") + name + (f" — {detail}" if detail and not cond else ""), flush=True)
    return bool(cond)


class WS:
    def __init__(self, session, token):
        self.s, self.token, self.n, self.events = session, token, 0, []

    async def __aenter__(self):
        self.ws = await self.s.ws_connect(WS_URL)
        await self.ws.receive_json()
        await self.ws.send_json({"type": "auth", "access_token": self.token})
        r = await self.ws.receive_json()
        assert r["type"] == "auth_ok", r
        return self

    async def __aexit__(self, *a):
        await self.ws.close()

    async def call(self, msg):
        self.n += 1
        mid = self.n
        await self.ws.send_json({**msg, "id": mid})
        while True:
            r = await self.ws.receive_json(timeout=60)
            if r.get("type") == "event":
                self.events.append(r["event"])
                continue
            if r.get("id") == mid:
                return r

    async def ok(self, msg):
        r = await self.call(msg)
        assert r.get("success"), r
        return r.get("result")


async def login(s, user, pwd):
    async with s.post(f"{BASE}/auth/login_flow", json={"client_id": CLIENT, "handler": ["homeassistant", None],
                                                          "redirect_uri": CLIENT}) as r:
        flow = await r.json()
    async with s.post(f"{BASE}/auth/login_flow/{flow['flow_id']}", json={"client_id": CLIENT, "username": user,
                                                                         "password": pwd}) as r:
        res = await r.json()
    async with s.post(f"{BASE}/auth/token", data={"grant_type": "authorization_code", "code": res["result"],
                                                   "client_id": CLIENT}) as r:
        return (await r.json())["access_token"]


async def setup(s) -> dict:
    """Onboarding + comptes + personnes + intégrations (une seule fois)."""
    try:
        st = json.load(open(STATE_FILE))
        for login_ in ("julie", "tabsalon", "invite", "liaison"):  # jetons courts (30 min) : renouvelés à chaque passage
            st[login_] = await login(s, login_, "motdepasse1")
        return st
    except OSError:
        pass
    async with s.post(f"{BASE}/api/onboarding/users", json={"client_id": CLIENT, "name": "Richard",
                                                            "username": "richard", "password": "motdepasse1",
                                                            "language": "fr"}) as r:
        code = (await r.json())["auth_code"]
    async with s.post(f"{BASE}/auth/token", data={"grant_type": "authorization_code", "code": code,
                                                   "client_id": CLIENT}) as r:
        tok = (await r.json())["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    for step in ("core_config", "analytics", "integration"):
        async with s.post(f"{BASE}/api/onboarding/{step}", headers=h,
                          json={"client_id": CLIENT, "redirect_uri": CLIENT} if step == "integration" else {}):
            pass
    st = {}
    async with WS(s, tok) as w:
        st["admin"] = await w.ok({"type": "auth/long_lived_access_token", "client_name": "banc", "lifespan": 365})
        me = await w.ok({"type": "auth/current_user"})
        users = {}
        for name, login_, admin in (("Julie", "julie", False), ("TabDomo Salon", "tabsalon", False),
                                    ("Invité", "invite", False), ("Liaison", "liaison", False)):
            u = await w.ok({"type": "config/auth/create", "name": name, "group_ids": [
                "system-admin" if admin else "system-users"], "local_only": False})
            await w.ok({"type": "config/auth_provider/homeassistant/create", "user_id": u["user"]["id"],
                        "username": login_, "password": "motdepasse1"})
            users[login_] = u["user"]["id"]
        persons = (await w.ok({"type": "person/list"}))["storage"]
        if not any(p.get("user_id") == me["id"] for p in persons):  # l'onboarding crée déjà la personne
            await w.ok({"type": "person/create", "name": "Richard", "user_id": me["id"]})
        await w.ok({"type": "person/create", "name": "Julie", "user_id": users["julie"]})
    for login_ in ("julie", "tabsalon", "invite", "liaison"):
        st[login_] = await login(s, login_, "motdepasse1")
    for dom in ("code_pin", "visiteurs"):
        async with s.post(f"{BASE}/api/config/config_entries/flow", headers=h, json={"handler": dom}) as r:
            f = await r.json()
        async with s.post(f"{BASE}/api/config/config_entries/flow/{f['flow_id']}", headers=h, json={}) as r:
            assert (await r.json())["type"] == "create_entry"
    json.dump(st, open(STATE_FILE, "w"))
    return st


async def options(s, tok, domain, data):
    h = {"Authorization": f"Bearer {tok}"}
    async with s.get(f"{BASE}/api/config/config_entries/entry", headers=h) as r:
        entry = next(e for e in await r.json() if e["domain"] == domain)
    async with s.post(f"{BASE}/api/config/config_entries/options/flow", headers=h,
                      json={"handler": entry["entry_id"]}) as r:
        f = await r.json()
    async with s.post(f"{BASE}/api/config/config_entries/options/flow/{f['flow_id']}", headers=h, json=data) as r:
        res = await r.json()
    assert res.get("type") == "create_entry", res
    await asyncio.sleep(2)  # rechargement


async def state(s, tok, eid):
    async with s.get(f"{BASE}/api/states/{eid}", headers={"Authorization": f"Bearer {tok}"}) as r:
        return await r.json() if r.status == 200 else None


async def svc(s, tok, domain, service, data, response=False):
    url = f"{BASE}/api/services/{domain}/{service}" + ("?return_response" if response else "")
    async with s.post(url, headers={"Authorization": f"Bearer {tok}"}, json=data) as r:
        body = await r.text()
        try:
            return r.status, json.loads(body)
        except ValueError:
            return r.status, body


def local(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


async def main() -> None:
    async with aiohttp.ClientSession() as s:
        st = await setup(s)
        A = st["admin"]
        if "--restart-phase" in sys.argv:
            return await after_restart(s, st)
        # ───────── réglages ─────────
        await options(s, A, "code_pin", {"mode": "observation", "motif_tablette": "TabDomo", "notifier": "",
                                         "comptes_exemptes": [], "comptes_liaison": []})
        async with WS(s, A) as w:
            labels = await w.ok({"type": "config/label_registry/list"})
            lab = next(x["label_id"] for x in labels if x["name"] == "Protégé par code")
            for eid in ("cover.porte_banc", "alarm_control_panel.alarme_banc"):
                await w.ok({"type": "config/entity_registry/update", "entity_id": eid, "labels": [lab]})
            # efface les visites d'un passage précédent du banc
            info = await w.ok({"type": "visiteurs/info", "jours": 90})
            for v in info["visites"]:
                await w.ok({"type": "visiteurs/supprimer", "visite": v["id"]})
            # code personnel de Richard (pour les cas « personne »)
            await w.call({"type": "code_pin/definir", "nouveau": "482917"})
        await options(s, A, "visiteurs", {
            "acces_proposes": ["cover.porte_banc", "alarm_control_panel.alarme_banc"], "wifi_ssid": "Invités Grange",
            "wifi_mot_de_passe": "bienvenue;2026", "wifi_securite": "WPA", "consignes": "Fermer le portail.",
            "lumiere_accueil": "input_boolean.lumiere", "duree_passage_h": 2, "duree_sur_place_h": 24,
            "marge_avant_min": 0, "marge_apres_min": 0, "nuit_debut": "22:00:00", "nuit_fin": "06:00:00",
            "prevenir": "tout", "niveau": "alerte", "notifier": "persistent_notification.create", "gestionnaires": [],
            "motif_tablette": "TabDomo"})
        ents = {}
        async with WS(s, A) as w:
            reg = await w.ok({"type": "config/entity_registry/list"})
            for e in reg:
                if e["platform"] == "visiteurs":
                    ents[e["translation_key"]] = e["entity_id"]
        check("entités créées (6)", set(ents) >= {"sur_place", "passage", "nuit", "en_cours", "prochaine", "agenda"},
              str(ents))
        SP, PA, EC, PR, AG = ents["sur_place"], ents["passage"], ents["en_cours"], ents["prochaine"], ents["agenda"]
        st0 = await state(s, A, SP)
        check("aucun invité au départ", st0["state"] == "off")

        # ───────── droits ─────────
        code, body = await svc(s, st["tabsalon"], "visiteurs", "ajouter", {"nom": "Pirate"}, response=True)
        check("tablette : ajout refusé", code in (401, 403), f"{code} {body}")
        code, body = await svc(s, st["invite"], "visiteurs", "ajouter", {"nom": "Pirate"}, response=True)
        check("compte sans personne : ajout refusé", code in (401, 403), f"{code} {body}")
        code, body = await svc(s, st["liaison"], "visiteurs", "ajouter", {"nom": "Via centrale", "type": "passage",
                                                                          "debut": "2030-01-01 10:00:00", "duree": 1})
        check("compte de liaison (centrale) : ajout accepté", code == 200, f"{code} {body}")
        async with WS(s, A) as w:
            info = await w.ok({"type": "visiteurs/info"})
            vc = next((v for v in info["visites"] if v["nom"] == "Via centrale"), None)
            check("visite de la centrale : créée par « Centrale »", vc and vc["creee_par"] == "Centrale", str(vc))
            if vc:
                await w.ok({"type": "visiteurs/supprimer", "visite": vc["id"]})
        async with WS(s, st["tabsalon"]) as w:
            r = await w.call({"type": "visiteurs/ajouter", "nom": "Pirate"})
            check("tablette : API carte refusée", not r.get("success"), str(r))
            info = await w.ok({"type": "visiteurs/info"})
            check("tablette : lecture accueil sans gestion", info["gestion"] is False and info["wifi"]["ssid"] ==
                  "Invités Grange" and info["acces"] == [] and "WIFI:T:WPA;S:Invités Grange;P:bienvenue\\;2026;;" ==
                  info["wifi"]["qr"], json.dumps(info)[:300])

        # ───────── passage immédiat avec code (Julie, non admin) ─────────
        code, body = await svc(s, st["julie"], "visiteurs", "ajouter", {
            "nom": "Marc", "type": "passage", "plaques": "ek 262 wq", "code": True,
            "acces": ["cover.porte_banc"]}, response=True)
        resp = (body or {}).get("service_response", {}) if isinstance(body, dict) else {}
        check("Julie ajoute un passage avec code", code == 200 and resp.get("code") and len(resp["code"]) == 6,
              f"{code} {body}")
        marc_id, marc_code = resp.get("id"), resp.get("code")
        check("message d'accueil complet", all(x in (resp.get("message") or "") for x in (
            "Bonjour Marc", marc_code or "?", "Porte banc", "Invités Grange", "bienvenue;2026", "Fermer le portail.")),
              resp.get("message"))
        await asyncio.sleep(1)
        pa = await state(s, A, PA)
        check("passage en cours", pa["state"] == "on" and pa["attributes"]["noms"] == ["Marc"], str(pa))
        check("invités sur place : non (passage)", (await state(s, A, SP))["state"] == "off")
        ec = await state(s, A, EC)
        check("compteur et plaques", ec["state"] == "1" and ec["attributes"]["plaques"] == {"EK-262-WQ": "Marc"},
              str(ec))
        check("lumière d'accueil : pas allumée de jour / selon soleil",
              (await state(s, A, "input_boolean.lumiere"))["state"] == (
                  "on" if (await state(s, A, "sun.sun"))["state"] == "below_horizon" else "off"))

        # ───────── tablette : code visiteur ─────────
        async with WS(s, st["tabsalon"]) as w:
            info = await w.ok({"type": "code_pin/info", "entites": ["cover.porte_banc"]})
            vis = [p for p in info["personnes"] if p["cle"] == "visiteur"]
            check("tablette : bouton « Visiteur » proposé", len(vis) == 1 and vis[0].get("visiteur"), str(info))
            r = await w.ok({"type": "code_pin/executer", "entity_id": "cover.porte_banc", "action": "ouvrir",
                            "personne": "visiteur", "code": "000000"})
            check("code visiteur faux refusé", r["ok"] is False and r["erreur"] == "code_faux", str(r))
            r = await w.ok({"type": "code_pin/executer", "entity_id": "cover.porte_banc", "action": "ouvrir",
                            "personne": "visiteur", "code": marc_code})
            check("code visiteur ouvre la porte", r["ok"] and "Marc (visiteur)" in r["qui"], str(r))
            await asyncio.sleep(1.5)
            check("porte ouverte", (await state(s, A, "cover.porte_banc"))["state"] == "open")
            r = await w.ok({"type": "code_pin/executer", "entity_id": "alarm_control_panel.alarme_banc",
                            "action": "desarmer", "personne": "visiteur", "code": marc_code})
            check("code visiteur : alarme non autorisée", r["ok"] is False and r["erreur"] == "visiteur_acces", str(r))
        async with WS(s, st["julie"]) as w:
            info = await w.ok({"type": "code_pin/info", "entites": []})
            check("téléphone de Julie : pas de bouton Visiteur", all(p["cle"] != "visiteur" for p in info["personnes"]))
        async with WS(s, A) as w:
            vi = await w.ok({"type": "visiteurs/info"})
            marc = next(v for v in vi["visites"] if v["id"] == marc_id)
            check("arrivée notée par le code", (marc.get("arrivee") or {}).get("source") == "code", str(marc))
            j = await w.ok({"type": "code_pin/journal", "jours": 1, "limite": 20})
            check("journal : ouverture par Marc (visiteur) (tablette Salon)", any(
                e["personne"] == "Marc (visiteur)" and e["resultat"] == "ok" and e["appareil"] == "Salon"
                for e in j["entrees"]), str(j["entrees"][:3]))
        # notification d'usage (persistent_notification)
        await asyncio.sleep(1)
        async with WS(s, A) as w:
            r = await w.call({"type": "persistent_notification/subscribe"})
            ev = None
            for _ in range(3):
                msg = await w.ws.receive_json(timeout=5)
                if msg.get("type") == "event":
                    ev = msg["event"]
                    break
            texts = json.dumps(ev, ensure_ascii=False) if ev else ""
            check("notification : usage du code signalé", "🔑 Marc : ouvrir Porte banc" in texts, texts[:300])
            check("notification : début de visite", "Visite de Marc" in texts, texts[:300])

        # ───────── plaque ─────────
        code, body = await svc(s, A, "visiteurs", "reconnaitre_plaque", {"plaques": ["EK262WO", "XX"]}, response=True)
        sr = body.get("service_response", {}) if isinstance(body, dict) else {}
        check("plaque reconnue (lecture approximative)", sr.get("trouve") and sr.get("nom") == "Marc", str(body))
        code, body = await svc(s, A, "visiteurs", "reconnaitre_plaque", {"plaques": "AB123CD"}, response=True)
        check("plaque inconnue", body.get("service_response", {}).get("trouve") is False, str(body))

        # ───────── invité sur place prévu, puis début automatique ─────────
        now = datetime.now()
        debut = now + timedelta(seconds=75)
        async with WS(s, A) as w:
            r = await w.ok({"type": "visiteurs/ajouter", "nom": "Mamie", "type_visite": "sur_place",
                            "debut": local(debut), "fin": local(debut + timedelta(days=2)), "code": False})
            mamie = r["visite"]
            check("séjour prévu enregistré", mamie["statut"] == "prevue" and not mamie.get("code"), str(r))
            pr = await state(s, A, PR)
            check("prochaine visite = Mamie", pr["attributes"].get("nom") == "Mamie", str(pr))
            await w.ok({"type": "subscribe_events", "event_type": "visiteurs_debut"})
            waited = time.time()
            ev = None
            while time.time() - waited < 120:
                try:
                    msg = await w.ws.receive_json(timeout=5)
                except asyncio.TimeoutError:
                    continue
                if msg.get("type") == "event" and msg["event"]["data"].get("nom") == "Mamie":
                    ev = msg["event"]
                    break
            late = time.time() - debut.timestamp()
            check("début annoncé à l'heure (≤ 3 s de retard)", ev is not None and -1 <= late <= 3, f"{late:.1f}s")
        sp = await state(s, A, SP)
        check("invités sur place = Mamie", sp["state"] == "on" and sp["attributes"]["noms"] == ["Mamie"], str(sp))

        # ───────── agenda ─────────
        start = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = (datetime.utcnow() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        async with s.get(f"{BASE}/api/calendars/{AG}?start={start}&end={end}",
                         headers={"Authorization": f"Bearer {A}"}) as r:
            evs = await r.json()
        check("agenda : 2 visites", sorted(e["summary"] for e in evs) == ["Mamie", "Marc"], str(evs))
        cstart = (now + timedelta(days=3)).replace(hour=9, minute=0, second=0, microsecond=0)
        code, body = await svc(s, A, "calendar", "create_event", {
            "entity_id": AG, "summary": "Plombier", "description": "passage",
            "start_date_time": local(cstart), "end_date_time": local(cstart + timedelta(hours=3))})
        async with WS(s, A) as w:
            vi = await w.ok({"type": "visiteurs/info"})
            plo = next((v for v in vi["visites"] if v["nom"] == "Plombier"), None)
            check("agenda : ajout d'une visite (passage)", plo and plo["type"] == "passage" and plo["statut"] ==
                  "prevue", f"{code} {body} {plo}")

        # ───────── modifier / prolonger / terminer ─────────
        async with WS(s, A) as w:
            r = await w.ok({"type": "visiteurs/modifier", "visite": marc_id,
                            "fin": local(datetime.now() + timedelta(hours=5))})
            check("prolonger Marc", r["ok"] and r["visite"]["statut"] == "en_cours", str(r))
            r = await w.ok({"type": "visiteurs/modifier", "visite": marc_id, "fin": local(datetime.now() -
                                                                                     timedelta(hours=1))})
            check("départ dans le passé refusé", r["ok"] is False, str(r))
            r = await w.ok({"type": "visiteurs/ajouter", "nom": "Test", "acces": ["lock.inconnue"], "code": True})
            check("accès non proposé refusé", r["ok"] is False and r["erreur"] == "acces", str(r))
            r = await w.ok({"type": "visiteurs/ajouter", "nom": "Test", "code": True})
            check("code sans accès refusé", r["ok"] is False, str(r))
            r = await w.ok({"type": "visiteurs/ajouter", "nom": "  ", "type_visite": "passage"})
            check("nom vide refusé", r["ok"] is False and r["erreur"] == "nom", str(r))
            r = await w.ok({"type": "visiteurs/ajouter", "nom": "Bob", "code": marc_code, "acces": ["cover.porte_banc"]})
            check("code déjà donné refusé", r["ok"] is False and r["erreur"] == "code", str(r))
            r = await w.ok({"type": "visiteurs/terminer", "visite": marc_id})
            check("terminer Marc", r["ok"])
        await asyncio.sleep(1)
        check("passage terminé", (await state(s, A, PA))["state"] == "off")
        async with WS(s, st["tabsalon"]) as w:
            info = await w.ok({"type": "code_pin/info", "entites": []})
            check("plus de bouton Visiteur", all(p["cle"] != "visiteur" for p in info["personnes"]))
            r = await w.ok({"type": "code_pin/executer", "entity_id": "cover.porte_banc", "action": "ouvrir",
                            "personne": "visiteur", "code": marc_code})
            check("code de Marc refusé après son départ", r["ok"] is False, str(r))
        async with WS(s, A) as w:
            vi = await w.ok({"type": "visiteurs/info"})
            m = next(v for v in vi["visites"] if v["id"] == marc_id)
            check("Marc dans « terminées » (historique)", m["statut"] == "terminee")
            r = await w.ok({"type": "visiteurs/modifier", "visite": marc_id, "fin": local(datetime.now() +
                                                                                     timedelta(hours=1))})
            check("Marc revient (rouvrir avec un départ)", r["ok"] and r["visite"]["statut"] == "en_cours", str(r))
            r = await w.ok({"type": "visiteurs/modifier", "visite": marc_id, "code": "nouveau"})
            check("nouveau code", r["ok"] and r["visite"]["code"] != marc_code, str(r))
            # blocage après 5 erreurs
        async with WS(s, st["tabsalon"]) as w:
            last = None
            for _ in range(5):
                last = await w.ok({"type": "code_pin/executer", "entity_id": "cover.porte_banc", "action": "ouvrir",
                                   "personne": "visiteur", "code": "135792"})
            check("5 erreurs : codes visiteur bloqués", last["erreur"] == "bloque", str(last))
        async with WS(s, A) as w:
            r = await w.ok({"type": "code_pin/debloquer", "personne": "visiteur", "code_admin": "482917"})
            check("déblocage par un admin", r["ok"], str(r))
        # ───────── passages réguliers (1.2) ─────────
        JL = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        t0 = datetime.now() - timedelta(minutes=5)
        t1 = datetime.now() + timedelta(minutes=40)
        jour = JL[t0.weekday()]
        fin_serie = (t0 + timedelta(days=14)).date().isoformat()
        async with WS(s, A) as w:
            await w.ok({"type": "subscribe_events", "event_type": "visiteurs_fin"})
            await w.ok({"type": "subscribe_events", "event_type": "visiteurs_debut"})
            code, body = await svc(s, st["julie"], "visiteurs", "ajouter", {
                "nom": "Maréchal", "type": "passage", "repetition_jours": [jour], "heure_debut": t0.strftime("%H:%M"),
                "heure_fin": t1.strftime("%H:%M"), "jusqu_au": fin_serie, "plaques": "GH-404-JK", "code": True,
                "acces": ["cover.porte_banc"]}, response=True)
            resp = (body or {}).get("service_response", {}) if isinstance(body, dict) else {}
            mar_id, mar_code = resp.get("id"), resp.get("code")
            check("série : ajout par l'action (Julie)", code == 200 and mar_id and mar_code, f"{code} {body}")
            check("série : message « Vos passages … jusqu'au »", "Vos passages" in (resp.get("message") or "") and
                  "pendant vos passages" in resp.get("message", ""), resp.get("message"))
            await asyncio.sleep(1)
            vi = await w.ok({"type": "visiteurs/info"})
            mar = next((v for v in vi["visites"] if v["id"] == mar_id), {})
            check("série : passage en cours maintenant", mar.get("statut") == "en_cours" and mar.get("recurrence", {})
                  .get("jours") == [t0.weekday()], str(mar))
            pa = await state(s, A, PA)
            check("série : capteur passage + plaque", "Maréchal" in pa["attributes"]["noms"] and "GH-404-JK" in
                  (await state(s, A, EC))["attributes"]["plaques"], str(pa))
            check("série : événement de début", any(e["data"].get("nom") == "Maréchal" and e["data"].get("regulier")
                                                    for e in w.events if e["event_type"] == "visiteurs_debut"))
        async with WS(s, st["tabsalon"]) as w:
            r = await w.ok({"type": "code_pin/executer", "entity_id": "cover.porte_banc", "action": "fermer",
                            "personne": "visiteur", "code": mar_code})
            check("série : le code marche pendant le passage", r["ok"], str(r))
        start = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = (datetime.utcnow() + timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
        async with s.get(f"{BASE}/api/calendars/{AG}?start={start}&end={end}",
                         headers={"Authorization": f"Bearer {A}"}) as r:
            evs = [e for e in await r.json() if e["summary"] == "Maréchal"]
        check("série : 3 passages dans l'agenda (J, J+7, J+14)", len(evs) == 3 and all(
            "FREQ=WEEKLY" in (e.get("rrule") or "") for e in evs), json.dumps(evs)[:400])
        async with WS(s, A) as w:
            await w.ok({"type": "subscribe_events", "event_type": "visiteurs_fin"})
            r = await w.ok({"type": "visiteurs/terminer", "visite": mar_id})
            await asyncio.sleep(1)
            check("série : « Parti·e » termine le passage (événement de fin)", r["ok"] and any(
                e["data"].get("nom") == "Maréchal" for e in w.events if e["event_type"] == "visiteurs_fin"), str(r))
            vi = await w.ok({"type": "visiteurs/info"})
            mar = next(v for v in vi["visites"] if v["id"] == mar_id)
            nxt = datetime.fromisoformat(mar["debut"]).astimezone()
            check("série : prochain passage dans 7 jours", mar["statut"] == "prevue" and
                  (nxt.date() - t0.date()).days == 7, str(mar))
        async with WS(s, st["tabsalon"]) as w:
            r = await w.ok({"type": "code_pin/executer", "entity_id": "cover.porte_banc", "action": "ouvrir",
                            "personne": "visiteur", "code": mar_code})
            check("série : code refusé hors passage", r["ok"] is False, str(r))
        async with WS(s, A) as w:
            r = await w.ok({"type": "visiteurs/sauter", "visite": mar_id})
            vi = await w.ok({"type": "visiteurs/info"})
            mar = next(v for v in vi["visites"] if v["id"] == mar_id)
            check("série : « Pas cette fois » → passage suivant (J+14)", r["ok"] and (
                datetime.fromisoformat(mar["debut"]).astimezone().date() - t0.date()).days == 14, str(mar))
            r = await w.ok({"type": "visiteurs/modifier", "visite": mar_id,
                            "jusqu_au": (t0 + timedelta(days=8)).date().isoformat()})
            check("série : plus aucun passage → refusé", r["ok"] is False and r["erreur"] == "repetition", str(r))
            r = await w.ok({"type": "visiteurs/modifier", "visite": mar_id, "toutes_les": 2,
                            "jusqu_au": (t0 + timedelta(days=60)).date().isoformat()})
            check("série : une semaine sur deux, prolongée", r["ok"] and r["visite"]["recurrence"]["toutes"] == 2,
                  str(r))
            r = await w.ok({"type": "visiteurs/ajouter", "nom": "Erreur", "repetition_jours": ["lundi"],
                            "heure_debut": "08:00", "heure_fin": "08:00"})
            check("série : horaires identiques refusés", r["ok"] is False and r["erreur"] == "repetition", str(r))
            r = await w.ok({"type": "visiteurs/ajouter", "nom": "Erreur", "repetition_jours": ["xyz"],
                            "heure_debut": "08:00", "heure_fin": "09:00"})
            check("série : jour inconnu refusé", r["ok"] is False and r["erreur"] == "repetition", str(r))
            # agenda : création d'une série, puis suppression « ce passage et les suivants »
            d0 = (datetime.now() + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
            r = await w.call({"type": "calendar/event/create", "entity_id": AG, "event": {
                "summary": "Ménage", "description": "passage", "dtstart": d0.isoformat(),
                "dtend": (d0 + timedelta(hours=2)).isoformat(),
                "rrule": f"FREQ=WEEKLY;BYDAY={['MO','TU','WE','TH','FR','SA','SU'][d0.weekday()]}"}})
            vi = await w.ok({"type": "visiteurs/info"})
            men = next((v for v in vi["visites"] if v["nom"] == "Ménage"), {})
            check("agenda : création d'une série (répétition chaque semaine)", r.get("success") and men.get(
                "recurrence", {}).get("de") == "14:00" and men.get("type") == "passage", f"{r} {men}")
            rid = (d0 + timedelta(days=14)).strftime("%Y%m%d")
            r = await w.call({"type": "calendar/event/delete", "entity_id": AG, "uid": men.get("id", "?"),
                              "recurrence_id": rid, "recurrence_range": "THISANDFUTURE"})
            async with s.get(f"{BASE}/api/calendars/{AG}?start={start}&end={(datetime.utcnow() + timedelta(days=60)).strftime('%Y-%m-%dT%H:%M:%SZ')}",
                             headers={"Authorization": f"Bearer {A}"}) as resp_:
                evs = [e for e in await resp_.json() if e["summary"] == "Ménage"]
            check("agenda : « ce passage et les suivants » → 2 passages restants", r.get("success") and len(evs) == 2,
                  f"{r} {len(evs)}")
            r = await w.call({"type": "calendar/event/delete", "entity_id": AG, "uid": men.get("id", "?"),
                              "recurrence_id": (d0 + timedelta(days=7)).strftime("%Y%m%d")})
            vi = await w.ok({"type": "visiteurs/info"})
            men = next((v for v in vi["visites"] if v["nom"] == "Ménage"), {})
            check("agenda : supprimer un seul passage → sauté", r.get("success") and len(men.get("sauf") or []) == 1,
                  f"{r} {men}")
            r = await w.ok({"type": "visiteurs/modifier", "visite": men["id"], "repetition_jours": [],
                            "debut": local(d0), "fin": local(d0 + timedelta(hours=1))})
            check("série → visite simple", r["ok"] and not r["visite"].get("recurrence"), str(r))
            await w.ok({"type": "visiteurs/supprimer", "visite": men["id"]})
        # ───────── passage régulier qui reste dormir (1.3) ─────────
        t0 = datetime.now() - timedelta(minutes=5)
        t1 = datetime.now() + timedelta(minutes=40)
        demain10 = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        async with WS(s, A) as w:
            r = await w.ok({"type": "visiteurs/ajouter", "nom": "Papa", "type_visite": "passage",
                            "repetition_jours": JL, "heure_debut": t0.strftime("%H:%M"), "heure_fin": t1.strftime("%H:%M"),
                            "code": True, "acces": ["cover.porte_banc"]})
            papa = r.get("visite", {})
            check("papa : passage tous les jours, en cours", r["ok"] and papa["statut"] == "en_cours" and
                  papa["type"] == "passage", str(r))
            await asyncio.sleep(1)
            await w.ok({"type": "subscribe_events", "event_type": "visiteurs_debut"})
            r = await w.ok({"type": "visiteurs/sejour", "visite": papa["id"], "fin": local(demain10)})
            pv = r.get("visite", {})
            check("papa dort ici : reste sur place jusqu'à demain 10 h", r["ok"] and pv["type"] == "sur_place" and
                  pv["dort_ici"] and datetime.fromisoformat(pv["fin"]).astimezone().replace(tzinfo=None) == demain10,
                  str(r))
            await asyncio.sleep(1)
            sp = await state(s, A, SP)
            pa = await state(s, A, PA)
            check("papa dort ici : compte comme invité sur place (plus en passage)", "Papa" in sp["attributes"]["noms"]
                  and "Papa" not in (pa["attributes"].get("noms") or []), f"{sp} {pa}")
            check("papa dort ici : pas de 2e annonce de début", not [e for e in w.events if e.get("event_type") ==
                                                                    "visiteurs_debut" and e["data"]["nom"] == "Papa"])
            r = await w.ok({"type": "visiteurs/sejour", "visite": mamie["id"], "fin": local(demain10)})
            check("« dort ici » refusé pour une visite simple (utiliser Modifier)", r["ok"] is False, str(r))
        async with WS(s, st["tabsalon"]) as w:
            r = await w.ok({"type": "code_pin/executer", "entity_id": "cover.porte_banc", "action": "fermer",
                            "personne": "visiteur", "code": papa["code"]})
            check("papa dort ici : même code", r["ok"], str(r))
        start = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        async with s.get(f"{BASE}/api/calendars/{AG}?start={start}&end={end}",
                         headers={"Authorization": f"Bearer {A}"}) as r:
            evs = [e for e in await r.json() if e["summary"] == "Papa (dort ici)"]
        check("agenda : la nuit de papa", len(evs) == 1, str(evs))
        async with WS(s, A) as w:
            r = await w.ok({"type": "visiteurs/sejour", "visite": papa["id"], "retirer": True})
            pv = r.get("visite", {})
            check("nuit annulée : de nouveau de passage jusqu'à la fin du créneau", r["ok"] and pv["type"] == "passage"
                  and not pv["sejours"] and datetime.fromisoformat(pv["fin"]).astimezone().strftime("%H:%M") ==
                  t1.strftime("%H:%M"), str(r))
            soir = (datetime.now() + timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
        code, body = await svc(s, st["julie"], "visiteurs", "sejour", {
            "id": papa["id"], "debut": local(soir), "fin": local(soir + timedelta(hours=13))})
        async with WS(s, A) as w:
            info = await w.ok({"type": "visiteurs/info"})
            pv = next(v for v in info["visites"] if v["id"] == papa["id"])
            check("nuit prévue demain soir (action, Julie) : passage du jour inchangé", code == 200 and
                  len(pv["sejours"]) == 1 and pv["type"] == "passage" and pv["statut"] == "en_cours", f"{code} {pv}")
            rid = "S" + soir.strftime("%Y%m%dT%H%M%S")
            r = await w.call({"type": "calendar/event/delete", "entity_id": AG, "uid": papa["id"], "recurrence_id": rid})
            info = await w.ok({"type": "visiteurs/info"})
            pv = next(v for v in info["visites"] if v["id"] == papa["id"])
            check("agenda : supprimer la nuit l'annule (la série reste)", r.get("success") and not pv["sejours"] and
                  pv.get("recurrence"), f"{r} {pv}")
            await w.ok({"type": "visiteurs/supprimer", "visite": papa["id"]})
        # ───────── réglages depuis le tableau de bord (1.1) ─────────
        async with WS(s, st["julie"]) as w:
            r = await w.ok({"type": "visiteurs/reglages"})
            check("réglages : refusés à Julie (non admin)", r["ok"] is False and r["erreur"] == "admin", str(r))
        async with WS(s, A) as w:
            await w.ok({"type": "subscribe_events", "event_type": "visiteurs_debut"})
            r = await w.ok({"type": "visiteurs/reglages"})
            check("réglages : lecture admin", r["ok"] and "regle_armement" in r["regles"] and any(
                a["entity_id"] == "cover.porte_banc" for a in r["acces_possibles"]), str(r)[:300])
            r = await w.ok({"type": "visiteurs/regler", "wifi_ssid": "Les Roches Invités", "wifi_generer": True})
            import re as _re
            pwd = r.get("valeurs", {}).get("wifi_mot_de_passe", "")
            check("Wi-Fi : mot de passe généré", r["ok"] and _re.fullmatch(r"[a-z2-9]{4}-[a-z2-9]{4}-[a-z2-9]{4}", pwd),
                  str(r)[:300])
            r = await w.ok({"type": "visiteurs/regler", "wifi_mot_de_passe": "court"})
            check("Wi-Fi : mot de passe trop court refusé", r["ok"] is False and r["erreur"] == "wifi", str(r))
            r = await w.ok({"type": "visiteurs/regler", "wifi_securite": "nopass"})
            info = await w.ok({"type": "visiteurs/info"})
            check("Wi-Fi ouvert : QR sans mot de passe", info["wifi"]["qr"] == "WIFI:T:nopass;S:Les Roches Invités;;",
                  info["wifi"]["qr"])
            await w.ok({"type": "visiteurs/regler", "wifi_securite": "WPA"})
            info = await w.ok({"type": "visiteurs/info"})
            check("Wi-Fi : QR mis à jour", info["wifi"]["qr"] == f"WIFI:T:WPA;S:Les Roches Invités;P:{pwd};;",
                  info["wifi"]["qr"])
            r = await w.ok({"type": "visiteurs/regler", "acces_proposes": ["cover.porte_banc"], "nuit_debut": "20:30:00",
                            "consignes": "Merci de fermer le portail.", "duree_passage_h": 3})
            info = await w.ok({"type": "visiteurs/info"})
            check("accès proposés et consignes appliqués", [a["entity_id"] for a in info["acces"]] == [
                "cover.porte_banc"] and info["consignes"] == "Merci de fermer le portail." and info["durees"][
                "passage"] == 3, str(info)[:300])
            r = await w.ok({"type": "visiteurs/regler", "acces_proposes": ["lock.nexiste_pas"]})
            check("accès inexistant refusé", r["ok"] is False and r["erreur"] == "acces", str(r))
            reg = await w.ok({"type": "config/entity_registry/list"})
            sw = {e["translation_key"]: e["entity_id"] for e in reg if e["platform"] == "visiteurs" and
                  e["entity_id"].startswith("switch.")}
            check("4 interrupteurs de comportement", len(sw) == 4, str(sw))
            await w.ok({"type": "call_service", "domain": "switch", "service": "turn_off",
                        "target": {"entity_id": sw["regle_armement"]}})
            await asyncio.sleep(1)
            r = await w.ok({"type": "visiteurs/reglages"})
            check("interrupteur → réglage enregistré", r["valeurs"]["regle_armement"] is False, str(r["valeurs"]))
            await w.ok({"type": "call_service", "domain": "switch", "service": "turn_on",
                        "target": {"entity_id": sw["regle_armement"]}})
            await asyncio.sleep(2)
            redo = [e for e in w.events if e.get("event_type") == "visiteurs_debut"]
            check("réglages : visites en cours non réannoncées", not redo, str(redo))
            info = await w.ok({"type": "visiteurs/info"})
            check("réglages : Marc toujours en cours", any(v["nom"] == "Marc" and v["statut"] == "en_cours"
                                                           for v in info["visites"]))
        async with WS(s, st["julie"]) as w:
            r = await w.call({"type": "call_service", "domain": "switch", "service": "turn_off",
                              "target": {"entity_id": sw["regle_armement"]}})
        check("interrupteur refusé à Julie", not r.get("success") and (await state(s, A, sw["regle_armement"]))[
            "state"] == "on", str(r))
        json.dump({**st, "mamie": mamie["id"], "marc": marc_id, "marechal": mar_id}, open(STATE_FILE, "w"))
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} contrôles OK")


async def after_restart(s, st) -> None:
    A = st["admin"]
    async with WS(s, A) as w:
        vi = await w.ok({"type": "visiteurs/info"})
        names = {v["nom"]: v["statut"] for v in vi["visites"]}
        check("après redémarrage : visites conservées", names.get("Mamie") == "en_cours" and names.get("Marc") ==
              "en_cours" and names.get("Plombier") == "prevue", str(names))
        reg = await w.ok({"type": "config/entity_registry/list"})
        sp = next(e["entity_id"] for e in reg if e["platform"] == "visiteurs" and e["translation_key"] == "sur_place")
    check("après redémarrage : invités sur place", (await state(s, A, sp))["state"] == "on")
    mar = next((v for v in vi["visites"] if v["nom"] == "Maréchal"), {})
    check("après redémarrage : série conservée (une semaine sur deux, 2 passages sautés)", mar.get("statut") ==
          "prevue" and mar.get("recurrence", {}).get("toutes") == 2 and len(mar.get("sauf") or []) == 2, str(mar))
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} contrôles OK")


if __name__ == "__main__":
    asyncio.run(main())
