"""Cartes « Visiteurs » et « Codes d'accès » dans Chromium (banc local, après bench_visiteurs.py)."""
import asyncio
import json
import os

import aiohttp
from playwright.async_api import async_playwright

HA = "http://127.0.0.1:8123"
CLIENT = f"{HA}/"
OUT = "/home/claude/banc/shots"
CHROME = os.environ.get("CHROME", "/usr/bin/google-chrome")
RESULTS = []
os.makedirs(OUT, exist_ok=True)


def check(name, cond, detail=""):
    RESULTS.append(bool(cond))
    print(("✅ " if cond else "❌ ") + name + (f" — {detail}" if detail and not cond else ""), flush=True)


async def login(s, user, pwd="motdepasse1"):
    async with s.post(f"{HA}/auth/login_flow", json={"client_id": CLIENT, "handler": ["homeassistant", None],
                                                       "redirect_uri": CLIENT}) as r:
        flow = await r.json()
    async with s.post(f"{HA}/auth/login_flow/{flow['flow_id']}", json={"client_id": CLIENT, "username": user,
                                                                       "password": pwd}) as r:
        res = await r.json()
    async with s.post(f"{HA}/auth/token", data={"grant_type": "authorization_code", "code": res["result"],
                                                 "client_id": CLIENT}) as r:
        return await r.json()


async def ws(s, token, msgs):
    out = []
    async with s.ws_connect(f"{HA}/api/websocket") as w:
        await w.receive_json()
        await w.send_json({"type": "auth", "access_token": token})
        await w.receive_json()
        for i, m in enumerate(msgs, 1):
            await w.send_json({**m, "id": i})
            while True:
                r = await w.receive_json()
                if r.get("id") == i and r.get("type") == "result":
                    out.append(r)
                    break
    return out


def storage_js(tok):
    data = {**tok, "hassUrl": HA, "clientId": CLIENT, "expires": 10 ** 13}
    return f"localStorage.setItem('hassTokens', {json.dumps(json.dumps(data))}); localStorage.setItem('selectedLanguage', '\"fr\"');"


async def page_for(browser, tok, width, height, path="/visiteurs-test/0"):
    ctx = await browser.new_context(viewport={"width": width, "height": height}, locale="fr-FR",
                                    timezone_id="Europe/Paris")
    await ctx.add_init_script(storage_js(tok))
    page = await ctx.new_page()
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    await page.goto(f"{HA}{path}", wait_until="networkidle")
    return ctx, page, errors


async def main():
    async with aiohttp.ClientSession() as s:
        rich = await login(s, "richard")
        tab = await login(s, "tabsalon")
        A = rich["access_token"]
        # tableau de test : carte Visiteurs (gestion), carte Accueil, carte Codes d'accès
        cfg = {"title": "Test", "views": [{"title": "V", "path": "0", "cards": [
            {"type": "custom:visiteurs-card"},
            {"type": "custom:visiteurs-card", "mode": "accueil"},
            {"type": "custom:code-pin-card", "title": "Accès", "entities": ["cover.porte_banc"]}]}]}
        r = await ws(s, A, [
            {"type": "lovelace/dashboards/list"},
        ])
        if not any(d["url_path"] == "visiteurs-test" for d in r[0]["result"]):
            await ws(s, A, [{"type": "lovelace/dashboards/create", "url_path": "visiteurs-test", "title": "Visiteurs test",
                             "mode": "storage", "require_admin": False, "show_in_sidebar": False}])
        await ws(s, A, [{"type": "lovelace/config/save", "url_path": "visiteurs-test", "config": cfg},
                        {"type": "input_boolean/list"}])
        await ws(s, A, [{"type": "visiteurs/regler", "acces_proposes": ["cover.porte_banc",
                                                                   "alarm_control_panel.alarme_banc"]}])
        info = (await ws(s, A, [{"type": "visiteurs/info"}]))[0]["result"]
        marc = next(v for v in info["visites"] if v["nom"] == "Marc")
        await ws(s, A, [{"type": "call_service", "domain": "cover", "service": "close_cover", "target": {"entity_id": "cover.porte_banc"}}])

        async with async_playwright() as p:
            browser = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
            # ───────── Richard, ordinateur ─────────
            ctx, page, errors = await page_for(browser, rich, 1280, 1000)
            card = page.locator("visiteurs-card").first
            await card.locator(".v").first.wait_for(timeout=30000)
            txt = await card.evaluate("(e) => e.shadowRoot.textContent")
            check("liste : en ce moment / à venir", "En ce moment" in txt and "Mamie" in txt and "Marc" in txt
                  and "À venir" in txt and "Plombier" in txt, txt[:400])
            await page.screenshot(path=f"{OUT}/1_liste.png", full_page=True)
            # code masqué puis affiché
            tag = card.locator(".tag.code").first
            check("code masqué par défaut", "••••••" in await tag.inner_text())
            await tag.click()
            check("code affiché au toucher", marc["code"] in await card.locator(".tag.code").first.inner_text())
            # ajout d'un passage avec code
            await card.locator('[data-a="nouveau"]').click()
            await card.locator("#nom").fill("Paul")
            await card.locator('[data-f="type"][data-v="passage"]').click()
            await card.locator('[data-f="choix"][data-v="2 h"]').click()
            await card.locator("#plaques").fill("fz 433 zl")
            await card.locator("#tel").fill("06 12 34 56 78")
            await card.locator("#code").check()
            await card.locator('[data-acc="cover.porte_banc"]').check()
            check("alarme non proposée sans accès alarme", await card.locator("#alarme").count() == 0)
            await card.locator('[data-acc="alarm_control_panel.alarme_banc"]').check()
            check("case « peut désarmer » quand l'alarme est cochée", await card.locator("#alarme").count() == 1)
            await card.locator('[data-acc="alarm_control_panel.alarme_banc"]').uncheck()
            await page.screenshot(path=f"{OUT}/2_formulaire.png")
            await card.locator('[data-a="enregistrer"]').click()
            await card.locator(".grandcode").wait_for(timeout=10000)
            code = (await card.locator(".grandcode").inner_text()).strip()
            msg = await card.locator("#msg").input_value()
            check("résultat : code et message", code.isdigit() and len(code) == 6 and "Bonjour Paul" in msg
                  and code in msg and "Wi-Fi :" in msg, msg)
            sms = await card.locator('a[href^="sms:"]').get_attribute("href")
            check("lien SMS vers le téléphone", sms and sms.startswith("sms:0612345678?body="), sms)
            await page.screenshot(path=f"{OUT}/3_resultat.png")
            await card.locator('[data-a="fermer"]').click()
            info = (await ws(s, A, [{"type": "visiteurs/info"}]))[0]["result"]
            paul = next((v for v in info["visites"] if v["nom"] == "Paul"), None)
            check("Paul enregistré (passage, 2 h, plaque, accès)", paul and paul["type"] == "passage" and paul[
                "plaques"] == ["FZ-433-ZL"] and paul["acces"] == ["cover.porte_banc"] and paul["statut"] == "en_cours",
                  str(paul))
            # +2 h puis départ (double appui)
            item = card.locator(".v", has_text="Paul")
            await item.locator('[data-a="plus"]').click()
            await asyncio.sleep(1)
            info = (await ws(s, A, [{"type": "visiteurs/info"}]))[0]["result"]
            paul2 = next(v for v in info["visites"] if v["nom"] == "Paul")
            from datetime import datetime
            delta = (datetime.fromisoformat(paul2["fin"]) - datetime.fromisoformat(paul["fin"])).total_seconds()
            check("+2 h", abs(delta - 7200) < 90, str(delta))
            item = card.locator(".v", has_text="Paul")
            await item.locator('[data-a="terminer"]').click()
            check("départ : demande de confirmation", "Confirmer" in await item.locator('[data-a="terminer"]').inner_text())
            await item.locator('[data-a="terminer"]').click()
            await asyncio.sleep(1)
            info = (await ws(s, A, [{"type": "visiteurs/info"}]))[0]["result"]
            check("Paul parti", next(v for v in info["visites"] if v["nom"] == "Paul")["statut"] == "terminee")
            # modifier Mamie (séjour en cours : pas de champ arrivée)
            item = card.locator(".v", has_text="Mamie")
            await item.locator('[data-a="modifier"]').click()
            check("séjour en cours : arrivée non modifiable", await card.locator("#debut").count() == 0
                  and await card.locator('[data-f="maintenant"]').count() == 0)
            await card.locator('[data-a="annuler"]').click()
            # passages réguliers (1.2)
            item = card.locator(".v", has_text="Maréchal")
            itxt = await item.inner_text()
            check("série : 🔁 jours et horaires, prochain passage", "🔁" in itxt and "prochain passage" in itxt
                  and "une semaine sur deux" in itxt, itxt)
            check("série : « Pas cette fois » et « Supprimer » proposés", await item.locator('[data-a="sauter"]').count()
                  == 1 and await item.locator('[data-a="supprimer"]').count() == 1 and await item.locator(
                      '[data-a="plus"]').count() == 0)
            await card.locator('[data-a="nouveau"]').click()
            await card.locator("#nom").fill("Jardinier")
            await card.locator('[data-f="regulier"][data-v="1"]').click()
            check("série : type « passage » choisi d'office", "on" in (await card.locator(
                '[data-f="type"][data-v="passage"]').get_attribute("class") or ""))
            check("série : pas de champs arrivée / départ", await card.locator('[data-f="maintenant"]').count() == 0
                  and await card.locator('[data-f="choix"]').count() == 0)
            for b in await card.locator('[data-f="jour"].on').all():
                await b.click()
            await card.locator('[data-a="enregistrer"]').click()
            check("série : au moins un jour exigé", "au moins un jour" in await card.locator(".err").inner_text())
            await card.locator('[data-f="jour"][data-v="2"]').click()
            await card.locator('[data-f="jour"][data-v="4"]').click()
            await card.locator("#rep_de").fill("09:00")
            await card.locator("#rep_a").fill("11:30")
            await card.locator('[data-f="toutes"][data-v="2"]').click()
            from datetime import date, timedelta as _td
            await card.locator("#rep_jusqu").fill((date.today() + _td(days=60)).isoformat())
            check("série : résumé lisible", "mercredi et vendredi (une semaine sur deux), 9 h – 11 h 30" in
                  await card.locator(".boite").inner_text(), await card.locator(".boite").inner_text())
            await page.screenshot(path=f"{OUT}/9_serie_formulaire.png")
            await card.locator('[data-a="enregistrer"]').click()
            await card.locator("#msg").wait_for(timeout=10000)
            msg = await card.locator("#msg").input_value()
            check("série : message « Vos passages »", "Vos passages" in msg and "mercredi et vendredi" in msg, msg)
            await card.locator('[data-a="fermer"]').click()
            info = (await ws(s, A, [{"type": "visiteurs/info"}]))[0]["result"]
            jar = next((v for v in info["visites"] if v["nom"] == "Jardinier"), {})
            check("série : enregistrée (mer. + ven., 9 h – 11 h 30, 1 sur 2)", jar.get("recurrence") == {
                "jours": [2, 4], "de": "09:00", "a": "11:30", "toutes": 2} and jar.get("type") == "passage", str(jar))
            await card.locator(".v", has_text="Jardinier").locator('[data-a="modifier"]').click()
            check("série : formulaire de modification prérempli", await card.locator("#rep_de").input_value() == "09:00"
                  and await card.locator('[data-f="jour"].on').count() == 2)
            await card.locator('[data-a="annuler"]').click()
            # « dort ici » (1.3)
            from datetime import datetime as _dt
            JLx = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
            t0, t1 = _dt.now() - _td(minutes=5), _dt.now() + _td(minutes=40)
            await ws(s, A, [{"type": "visiteurs/ajouter", "nom": "Papa", "type_visite": "passage", "repetition_jours": JLx,
                             "heure_debut": t0.strftime("%H:%M"), "heure_fin": t1.strftime("%H:%M")}])
            await card.locator(".v", has_text="Papa").wait_for(timeout=70000)
            await card.locator(".v", has_text="Papa").locator('[data-a="nuit"]').click()
            check("dort ici : passage en cours → pas d'heure d'arrivée à saisir", await card.locator("#s_debut").count() == 0
                  and await card.locator("#s_fin").count() == 1)
            await card.locator('[data-s]', has_text="Demain matin").click()
            await page.screenshot(path=f"{OUT}/11_dort_ici.png")
            await card.locator('[data-a="s_ok"]').click()
            await page.wait_for_timeout(1500)
            info = (await ws(s, A, [{"type": "visiteurs/info"}]))[0]["result"]
            pv = next(v for v in info["visites"] if v["nom"] == "Papa")
            fin = _dt.fromisoformat(pv["fin"]).astimezone()
            check("dort ici : reste sur place jusqu'à demain 10 h", pv["type"] == "sur_place" and fin.hour == 10 and
                  (fin.date() - _dt.now().date()).days == 1, str(pv))
            it = card.locator(".v", has_text="Papa")
            check("dort ici : affiché dans la liste", "🛏️ dort ici, jusqu'à demain 10 h" in await it.inner_text(),
                  await it.inner_text())
            await page.screenshot(path=f"{OUT}/12_papa_liste.png")
            await it.locator('[data-a="sansnuit"]').click()
            await it.locator('[data-a="sansnuit"]').click()
            await page.wait_for_timeout(1500)
            info = (await ws(s, A, [{"type": "visiteurs/info"}]))[0]["result"]
            pv = next(v for v in info["visites"] if v["nom"] == "Papa")
            check("annuler la nuit (double appui) : de nouveau de passage", pv["type"] == "passage" and not pv["sejours"], str(pv))
            await card.locator(".v", has_text="Jardinier").locator('[data-a="nuit"]').click()
            check("dort ici sur un passage à venir : heure d'arrivée proposée", await card.locator("#s_debut").count() == 1)
            await card.locator('[data-a="s_annuler"]').click()
            await ws(s, A, [{"type": "visiteurs/supprimer", "visite": pv["id"]}])
            # formulaire : erreurs
            await card.locator('[data-a="nouveau"]').click()
            await card.locator('[data-a="enregistrer"]').click()
            check("nom obligatoire", "Indiquer le nom" in await card.locator(".err").inner_text())
            await card.locator('[data-a="annuler"]').click()
            # réglages (admin)
            await card.locator('[data-a="reglages"]').click()
            await card.locator("#r_mdp").wait_for(timeout=10000)
            before = await card.locator("#r_mdp").input_value()
            await card.locator('[data-a="r_gen"]').click()
            await page.wait_for_timeout(1500)
            after = await card.locator("#r_mdp").input_value()
            check("réglages : 🎲 génère un nouveau mot de passe", after and after != before, f"{before} → {after}")
            await card.locator("#r_cons").fill("Fermez le portail, merci.")
            await card.locator('[data-rb="regle_passage_info"]').uncheck()
            await card.locator('[data-rs="prevenir"][data-v="codes"]').click()
            check("réglages : saisie conservée après un choix", await card.locator("#r_cons").input_value() ==
                  "Fermez le portail, merci.")
            await page.screenshot(path=f"{OUT}/8_reglages.png")
            await card.locator('[data-a="r_enregistrer"]').click()
            await page.wait_for_timeout(1500)
            rg = (await ws(s, A, [{"type": "visiteurs/reglages"}]))[0]["result"]["valeurs"]
            check("réglages enregistrés (consignes, interrupteur, prévenir)", rg["consignes"] == "Fermez le portail, merci."
                  and rg["regle_passage_info"] is False and rg["prevenir"] == "codes" and rg["wifi_mot_de_passe"] == after,
                  str(rg))
            await ws(s, A, [{"type": "visiteurs/regler", "regle_passage_info": True, "prevenir": "tout"}])
            check("aucune erreur console (ordinateur)", not [e for e in errors if "visiteurs" in e.lower()
                                                            or "code-pin" in e.lower()], str(errors[:5]))
            await ctx.close()

            # ───────── Richard, téléphone 380 px ─────────
            ctx, page, errors = await page_for(browser, rich, 380, 800)
            card = page.locator("visiteurs-card").first
            await card.locator(".v").first.wait_for(timeout=30000)
            await card.locator('[data-a="nouveau"]').click()
            await card.locator("#nom").fill("Léa")
            await card.locator('[data-f="maintenant"][data-v="0"]').click()
            check("téléphone : arrivée « plus tard » affiche la date", await card.locator("#debut").count() == 1)
            box = await card.locator(".boite").bounding_box()
            check("téléphone : formulaire dans l'écran", box and box["width"] <= 380 and box["x"] >= 0, str(box))
            await page.screenshot(path=f"{OUT}/4_telephone_formulaire.png")
            await card.locator('[data-f="regulier"][data-v="1"]').click()
            box = await card.locator(".boite").bounding_box()
            check("téléphone : formulaire « régulièrement » dans l'écran", box and box["width"] <= 380, str(box))
            await page.screenshot(path=f"{OUT}/10_telephone_serie.png", full_page=False)
            await card.locator('[data-a="annuler"]').click()
            await page.screenshot(path=f"{OUT}/5_telephone_liste.png", full_page=True)
            await ctx.close()

            # ───────── tablette : accueil + code visiteur ─────────
            ctx, page, errors = await page_for(browser, tab, 1024, 768)
            cards = page.locator("visiteurs-card")
            await cards.first.locator(".accueil").wait_for(timeout=30000)
            t = await cards.first.evaluate("(e) => e.shadowRoot.textContent")
            check("tablette : mode accueil automatique", "Bienvenue" in t and "Mamie" in t and "Marc" in t, t)
            check("tablette : QR code Wi-Fi", await cards.first.locator(".qr svg").count() == 1)
            check("tablette : mot de passe et consignes", after in t and "Fermez le portail, merci." in t, t)
            check("tablette : aucun bouton de gestion", await cards.first.locator('[data-a="nouveau"]').count() == 0
                  and await cards.first.locator('[data-a="reglages"]').count() == 0)
            await page.screenshot(path=f"{OUT}/6_tablette_accueil.png", full_page=True)
            cp = page.locator("code-pin-card")
            await cp.locator("button", has_text="Ouvrir").first.click()
            modal = page.locator("code-pin-modal, body > *").filter(has=page.locator(".boite")).first
            await page.wait_for_timeout(800)
            vis = page.locator('[data-p="visiteur"]')
            check("tablette : 🔑 Visiteur proposé", await vis.count() == 1)
            await page.screenshot(path=f"{OUT}/7_tablette_qui.png")
            await vis.click()
            for d in marc["code"]:
                await page.locator(f'[data-d="{d}"]').click()
            await page.locator('[data-k="ok"]').click()
            await page.wait_for_timeout(2500)
            async with s.get(f"{HA}/api/states/cover.porte_banc", headers={"Authorization": f"Bearer {A}"}) as r:
                stt = (await r.json())["state"]
            check("tablette : porte ouverte avec le code de Marc", stt == "open", stt)
            check("aucune erreur console (tablette)", not [e for e in errors if "visiteurs" in e.lower()
                                                          or "code-pin" in e.lower()], str(errors[:5]))
            _ = modal
            await ctx.close()
            await browser.close()
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} contrôles OK")


asyncio.run(main())
