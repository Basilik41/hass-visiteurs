"""Codes visiteur sur les lecteurs UniFi Access.

Pendant chaque visite (ou chaque passage d'une visite régulière) qui a un code visiteur et au moins une porte
UniFi Access cochée, un « visiteur » UniFi Access est créé avec ce code (PIN) et ces portes, valable le temps de la
visite (marges comprises). Il est supprimé à la fin de la visite. Le lecteur ne connaît donc le code que pendant
les créneaux prévus, même si Home Assistant s'arrête (le visiteur UniFi a lui-même une heure de fin).

Connexion : celle de l'intégration UniFi Access de Home Assistant (adresse et jeton API). Le jeton doit avoir les
droits « view:visitor » et « edit:visitor » (UniFi Access › Paramètres › Général › Avancé › Jeton API).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import aiohttp
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .visites import parse_dt

if TYPE_CHECKING:
    from .manager import Visiteurs

_LOGGER = logging.getLogger(__name__)
PORT = 12445
MARQUE = "Home Assistant · Visiteurs"   # dans les « remarques » des visiteurs UniFi créés par le module
SUFFIXE = "-unlock"                     # unique_id des boutons « Déverrouiller » de l'intégration UniFi Access
PLATFORM = "unifi_access"


class AccessError(Exception):
    """Refus ou panne de l'API UniFi Access (message lisible)."""


def door_id(hass, entity_id: str) -> str | None:
    """Porte UniFi Access derrière une entité (bouton « Déverrouiller » de l'intégration UniFi Access)."""
    ent = er.async_get(hass).async_get(entity_id)
    if ent is None or ent.platform != PLATFORM or not (ent.unique_id or "").endswith(SUFFIXE):
        return None
    return ent.unique_id[: -len(SUFFIXE)]


def is_access_entity(hass, entity_id: str) -> bool:
    return door_id(hass, entity_id) is not None


def signature(pin: str, doors: list[str], start: int, end: int, nom: str) -> str:
    raw = "|".join([pin, ",".join(sorted(doors)), str(start), str(end), nom])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class AccessSync:
    def __init__(self, mgr: Visiteurs) -> None:
        self.m, self.hass = mgr, mgr.hass
        self._lock = asyncio.Lock()
        self.last_error: str | None = None
        self._told: str | None = None       # dernière erreur signalée (pas de répétition)
        self._cleaned = False

    # ───────── connexion ─────────
    def _config(self) -> tuple[str, str, bool] | None:
        for entry in self.hass.config_entries.async_entries(PLATFORM):
            if entry.disabled_by is None and entry.data.get("host") and entry.data.get("api_token"):
                return entry.data["host"], entry.data["api_token"], bool(entry.data.get("verify_ssl", False))
        return None

    @property
    def available(self) -> bool:
        return self._config() is not None

    async def _req(self, method: str, path: str, body: Any = None, params: dict | None = None) -> Any:
        cfg = self._config()
        if cfg is None:
            raise AccessError("Intégration UniFi Access absente.")
        host, token, verify = cfg
        url_host = f"[{host}]" if ":" in host else host
        session = async_get_clientsession(self.hass, verify_ssl=verify)
        try:
            async with session.request(method, f"https://{url_host}:{PORT}/api/v1/developer{path}", json=body,
                                       params=params, ssl=None if verify else False,
                                       headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                                       timeout=aiohttp.ClientTimeout(total=15)) as r:
                try:
                    data = await r.json(content_type=None)
                except ValueError:
                    data = None
                if r.status in (401, 403):
                    raise AccessError("Jeton UniFi Access refusé : il lui faut les droits « visiteurs » "
                                      "(view:visitor et edit:visitor).")
                if r.status >= 400 or not isinstance(data, dict) or data.get("code") != "SUCCESS":
                    msg = (data or {}).get("msg") if isinstance(data, dict) else None
                    code = (data or {}).get("code") if isinstance(data, dict) else None
                    raise AccessError(f"UniFi Access : {msg or code or f'erreur HTTP {r.status}'}")
                return data.get("data")
        except aiohttp.ClientError as err:
            raise AccessError(f"UniFi Access injoignable ({host}) : {err}") from err
        except TimeoutError as err:
            raise AccessError(f"UniFi Access ne répond pas ({host}).") from err

    # ───────── diagnostic (réglages) ─────────
    async def check(self) -> dict:
        """Ce que voit le module : portes, et droit de gérer les visiteurs."""
        if not self.available:
            return {"ok": False, "message": "Intégration UniFi Access non installée sur ce site."}
        try:
            doors = await self._req("GET", "/doors")
            await self._req("GET", "/visitors", params={"page_num": 1, "page_size": 1})
        except AccessError as err:
            return {"ok": False, "message": str(err)}
        return {"ok": True, "portes": [{"id": d.get("id"), "nom": d.get("full_name") or d.get("name")}
                                       for d in doors or []]}

    async def essai(self, pin: str) -> list[str]:
        """Essai complet sans toucher aux visites : PIN proposé par UniFi, visiteur de test (demain), code de
        la visite puis code proposé, suppression. Sert à comprendre un refus du lecteur."""
        import time as _t
        steps: list[str] = []
        gen = None
        try:
            gen = await self._req("POST", "/credentials/pin_codes")
            steps.append(f"PIN proposé par UniFi : {len(str(gen))} chiffres")
        except AccessError as err:
            steps.append(f"PIN proposé par UniFi : impossible ({err})")
        now = int(_t.time())
        try:
            data = await self._req("POST", "/visitors", {
                "first_name": "Essai", "last_name": "(visiteur)", "remarks": MARQUE, "start_time": now + 86400,
                "end_time": now + 90000, "visit_reason": "Others", "resources": []})
            vid = data.get("id")
            steps.append("création d'un visiteur : OK")
        except AccessError as err:
            return [*steps, f"création d'un visiteur : refusée ({err})"]
        for label, code in ((f"code de {len(pin)} chiffres", pin), ("PIN proposé", str(gen) if gen else None)):
            if not code:
                continue
            try:
                await self._req("PUT", f"/visitors/{vid}/pin_codes", {"pin_code": code})
                steps.append(f"{label} : accepté")
            except AccessError as err:
                steps.append(f"{label} : refusé ({err})")
        try:
            await self._delete(vid)
            steps.append("suppression : OK")
        except AccessError as err:
            steps.append(f"suppression : refusée ({err})")
        return steps

    # ───────── synchronisation ─────────
    def _desired(self) -> dict[str, dict]:
        out = {}
        for v in self.m.current():
            pin = v.get("code")
            doors = sorted({d for d in (door_id(self.hass, e) for e in v.get("acces") or []) if d})
            d, f = parse_dt(v.get("debut")), parse_dt(v.get("fin"))
            if not pin or not doors or d is None or f is None:
                continue
            start = int((d - timedelta(minutes=0 if v.get("immediate") else self.m.avant)).timestamp())
            end = int((f + timedelta(minutes=self.m.apres)).timestamp())
            nom = v.get("nom") or "Visiteur"
            out[v["id"]] = {"pin": pin, "doors": doors, "start": start, "end": end, "nom": nom,
                            "sig": signature(pin, doors, start, end, nom)}
        return out

    async def sync(self) -> None:
        """Aligne les visiteurs UniFi Access sur les visites en cours. Sans effet si rien n'est concerné."""
        if self._lock.locked():
            return
        async with self._lock:
            have: dict[str, dict] = self.m.unifi
            want = self._desired()
            if not want and not have:
                self.last_error = self._told = None
                return
            if not self.available:
                self._error("Des visites ont un accès UniFi Access, mais l'intégration UniFi Access n'est pas "
                            "chargée : les codes ne sont pas sur les lecteurs.")
                return
            changed, errors = False, []
            for vid in [k for k in have if k not in want or have[k].get("sig") != want[k]["sig"]]:
                try:
                    await self._delete(have[vid]["id"])
                except AccessError as err:
                    if "not" not in str(err).lower() or "found" not in str(err).lower():
                        errors.append(str(err))
                        continue
                have.pop(vid)
                changed = True
            for vid, w in want.items():
                if vid in have:
                    continue
                try:
                    have[vid] = {"id": await self._create(w), "sig": w["sig"]}
                    changed = True
                except AccessError as err:
                    errors.append(f"{w['nom']} : {err}")
            if not self._cleaned:
                await self._clean_orphans(set(x["id"] for x in have.values()))
            if changed:
                await self.m.save_unifi()
                self.m._notify_listeners()  # attribut « sur_lecteur » des capteurs → la carte se met à jour
            if errors:
                self._error(" ; ".join(errors))
            else:
                self.last_error = None
                self._told = None

    async def _create(self, w: dict) -> str:
        body = {"first_name": w["nom"][:30], "last_name": "(visiteur)", "remarks": MARQUE,
                "start_time": w["start"], "end_time": w["end"], "visit_reason": "Others",
                "resources": [{"id": d, "type": "door"} for d in w["doors"]]}
        data = await self._req("POST", "/visitors", body)
        vid = (data or {}).get("id") if isinstance(data, dict) else None
        if not vid:
            raise AccessError("UniFi Access n'a pas renvoyé d'identifiant de visiteur.")
        try:
            await self._req("PUT", f"/visitors/{vid}/pin_codes", {"pin_code": w["pin"]})
        except AccessError as err:
            try:
                await self._delete(vid)
            except AccessError:
                pass
            raise AccessError(f"code refusé par UniFi Access ({err}) — déjà utilisé par quelqu'un, ou longueur "
                              "non autorisée : changer le code de la visite") from err
        return vid

    async def _delete(self, visitor_id: str) -> None:
        await self._req("DELETE", f"/visitors/{visitor_id}", params={"is_force": "true"})

    async def _clean_orphans(self, keep: set[str]) -> None:
        """Visiteurs UniFi laissés par le module (arrêt de HA au mauvais moment) : supprimés une fois."""
        try:
            page = await self._req("GET", "/visitors", params={"page_num": 1, "page_size": 200})
        except AccessError:
            return  # droit de lecture absent : on réessaiera
        for x in page or []:
            if MARQUE in str(x.get("remarks") or "") and x.get("id") not in keep:
                try:
                    await self._delete(x["id"])
                except AccessError:
                    pass
        self._cleaned = True

    async def remove_all(self) -> None:
        """Désinstallation du module : plus aucun code sur les lecteurs."""
        for vid, x in list(self.m.unifi.items()):
            try:
                await self._delete(x["id"])
                self.m.unifi.pop(vid, None)
            except AccessError:
                pass

    def _error(self, msg: str) -> None:
        self.last_error = msg
        _LOGGER.warning("%s", msg)
        if msg != self._told:
            self._told = msg
            self.hass.async_create_task(self.m.send_admin(f"⚠️ Visiteurs › UniFi Access : {msg}"))
