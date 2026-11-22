"""Visiteurs : stockage des visites, créneaux, événements, notifications, lumière d'accueil, codes visiteur."""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CODE_PIN_PROVIDER,
    CONF_ACCES,
    CONF_CONSIGNES,
    CONF_DUREE_PASSAGE,
    CONF_DUREE_SUR_PLACE,
    CONF_LUMIERE,
    CONF_MARGE_APRES,
    CONF_MARGE_AVANT,
    CONF_NIVEAU,
    CONF_NOTIFY,
    CONF_NUIT_DEBUT,
    CONF_NUIT_FIN,
    CONF_PREVENIR,
    CONF_WIFI_MDP,
    CONF_WIFI_SECU,
    CONF_WIFI_SSID,
    DEFAULTS,
    DOMAIN,
    EVENT_CHANGE,
    EVENT_DEBUT,
    EVENT_FIN,
    HISTORY_DAYS,
    MAX_VISITES,
    PASSAGE,
    REFRESH_SECONDS,
    STORE_KEY,
    STORE_VERSION,
    SUR_PLACE,
    TYPE_LABELS,
)
from .visites import (
    EN_COURS,
    SAUF_MAX,
    SERIE_MAX_JOURS,
    TERMINEE,
    accueil_message,
    actives,
    clean_name,
    code_problem,
    effective,
    generate_code,
    in_night,
    match_plate,
    next_boundary,
    norm_recurrence,
    occurrence,
    parse_dt,
    plate_list,
    prochaines,
    purge,
    statut,
    validate_type,
    wifi_qr,
)

# champs des passages réguliers (actions, API de la carte)
SERIE_CHAMPS = ("repetition_jours", "heure_debut", "heure_fin", "toutes_les", "jusqu_au")

_LOGGER = logging.getLogger(__name__)
PBKDF2_ITERATIONS = 120_000  # même format que le module Codes d'accès


class VisiteError(ServiceValidationError):
    """Refus expliqué (champ manquant, visite inconnue…)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


def _hash(pin: str) -> dict[str, Any]:
    salt = os.urandom(16)
    return {"h": hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, PBKDF2_ITERATIONS).hex(), "s": salt.hex(),
            "i": PBKDF2_ITERATIONS}


class Visiteurs:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass, self.entry = hass, entry
        self.quiet_update = False  # réglage changé depuis le tableau de bord : pas de rechargement
        self._load_options()
        self._store: Store = Store(hass, STORE_VERSION, STORE_KEY, private=True, atomic_writes=True)
        self.visites: dict[str, dict] = {}
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._wake: CALLBACK_TYPE | None = None
        self._actives: dict[str, dict] = {}  # visites en cours (vue « passage » pour les séries)
        self._started = False

    def _load_options(self) -> None:
        self.o = {**DEFAULTS, **self.entry.data, **self.entry.options}
        self.avant = int(self.o.get(CONF_MARGE_AVANT) or 0)
        self.apres = int(self.o.get(CONF_MARGE_APRES) or 0)

    async def apply_settings(self, changes: dict[str, Any]) -> None:
        """Réglages modifiés depuis la carte ou un interrupteur : enregistrés dans les options, appliqués tout de
        suite, sans recharger le module (les visites en cours ne sont pas réannoncées)."""
        new = {**self.entry.options}
        for k, v in changes.items():
            if v is None or v == "":
                new.pop(k, None)
            else:
                new[k] = v
        if new == dict(self.entry.options):
            return
        self.quiet_update = True
        self.hass.config_entries.async_update_entry(self.entry, options=new)
        self._load_options()
        await self._refresh()

    # ───────── démarrage ─────────
    async def async_start(self) -> None:
        data = await self._store.async_load() or {}
        self.visites = {k: v for k, v in (data.get("visites") or {}).items() if isinstance(v, dict)}
        now = dt_util.utcnow()
        # Au démarrage : pas d'événement « début » pour les visites déjà en cours (rien de manqué à annoncer)
        self._actives = {v["id"]: v for v in actives(self._all(now), now, self.avant, self.apres)}
        self._unsubs += [
            async_track_time_interval(self.hass, self._tick, timedelta(seconds=REFRESH_SECONDS)),
            async_track_time_change(self.hass, self._lights_off, hour=23, minute=0, second=0),
        ]
        self.hass.data[CODE_PIN_PROVIDER] = self
        self._started = True
        self._schedule()

    async def async_stop(self) -> None:
        for u in self._unsubs:
            u()
        self._unsubs.clear()
        if self._wake:
            self._wake()
            self._wake = None
        if self.hass.data.get(CODE_PIN_PROVIDER) is self:
            self.hass.data.pop(CODE_PIN_PROVIDER, None)
        await self._save()

    async def _save(self) -> None:
        await self._store.async_save({"visites": self.visites})

    # ───────── abonnements des entités ─────────
    @callback
    def async_add_listener(self, cb: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.append(cb)

        @callback
        def remove() -> None:
            if cb in self._listeners:
                self._listeners.remove(cb)
        return remove

    @callback
    def _notify_listeners(self) -> None:
        for cb in list(self._listeners):
            cb()

    # ───────── horloge ─────────
    @callback
    def _schedule(self) -> None:
        if self._wake:
            self._wake()
            self._wake = None
        now = dt_util.utcnow()
        nxt = next_boundary(self._all(now), now, self.avant, self.apres)
        if nxt is not None:
            self._wake = async_track_point_in_utc_time(self.hass, self._tick, nxt + timedelta(seconds=1))

    async def _tick(self, _now: Any = None) -> None:
        await self._refresh()

    async def _refresh(self, changed: bool = False) -> None:
        """Recalcule les visites en cours ; annonce les débuts et fins ; prévient les entités."""
        now = dt_util.utcnow()
        cur = {v["id"]: v for v in actives(self._all(now), now, self.avant, self.apres)}
        started = [cur[i] for i in cur.keys() - self._actives.keys()]
        # une série passe d'un passage au suivant sans « trou » : fin de l'un puis début de l'autre
        started += [cur[i] for i in cur.keys() & self._actives.keys() if cur[i].get("debut") != self._actives[i].get("debut")]
        ended = [self._actives[i] for i in self._actives.keys() - cur.keys()]
        ended += [self._actives[i] for i in cur.keys() & self._actives.keys()
                  if cur[i].get("debut") != self._actives[i].get("debut")]
        self._actives = cur
        # entités à jour AVANT les événements : une automatisation déclenchée par « visiteurs_debut » lit le bon état
        self._notify_listeners()
        for v in ended:
            self.hass.bus.async_fire(EVENT_FIN, self._event_data(v))
            await self._on_end(v)
        for v in started:
            self.hass.bus.async_fire(EVENT_DEBUT, self._event_data(v))
            await self._on_start(v)
        before = len(self.visites)
        kept = purge(self._all(now), now, self.avant, self.apres, HISTORY_DAYS, MAX_VISITES)
        self.visites = {k: self.visites[k] for k in kept}
        if changed or started or ended or before != len(self.visites):
            await self._save()
        self._schedule()
        self._notify_listeners()

    def _event_data(self, v: dict) -> dict:
        return {"id": v["id"], "nom": v.get("nom"), "type": v.get("type"), "debut": v.get("debut"),
                "fin": v.get("fin"), "regulier": bool(v.get("recurrence")), "site": self.hass.config.location_name}

    # ───────── lecture ─────────
    def now(self) -> datetime:
        return dt_util.utcnow()

    def tz(self):
        return dt_util.get_default_time_zone()

    def eff(self, v: dict, now: datetime | None = None) -> dict:
        """Visite telle qu'elle se présente maintenant (série : passage en cours ou prochain)."""
        return effective(v, now or self.now(), self.tz(), self.avant, self.apres)

    def _all(self, now: datetime | None = None) -> dict[str, dict]:
        now = now or self.now()
        return {k: self.eff(v, now) for k, v in self.visites.items()}

    def status(self, v: dict) -> str:
        return statut(self.eff(v), self.now(), self.avant, self.apres)

    def current(self) -> list[dict]:
        return actives(self._all(), self.now(), self.avant, self.apres)

    def upcoming(self) -> list[dict]:
        return prochaines(self._all(), self.now(), self.avant, self.apres)

    def sur_place(self) -> list[dict]:
        return [v for v in self.current() if v.get("type") == SUR_PLACE]

    def passages(self) -> list[dict]:
        return [v for v in self.current() if v.get("type") == PASSAGE]

    def plates(self) -> dict[str, str]:
        return {p: v.get("nom") or "" for v in self.current() for p in v.get("plaques") or []}

    def is_night(self) -> bool:
        return in_night(dt_util.now(), self.o.get(CONF_NUIT_DEBUT), self.o.get(CONF_NUIT_FIN))

    def public(self, v: dict, admin: bool) -> dict:
        """Visite telle que la carte la voit. Le code n'est montré qu'aux administrateurs."""
        v = self.eff(v)
        out = {k: v.get(k) for k in ("id", "nom", "type", "debut", "fin", "plaques", "telephone", "note", "acces",
                                     "alarme", "arrivee", "terminee", "creee_par", "creee_le", "immediate",
                                     "recurrence", "serie_debut", "serie_fin")}
        out["sauf"] = list(v.get("sauf") or [])
        out["statut"] = statut(v, self.now(), self.avant, self.apres)
        out["a_un_code"] = bool(v.get("code"))
        if admin:
            out["code"] = v.get("code")
        return out

    def wifi(self) -> dict:
        ssid, pwd = self.o.get(CONF_WIFI_SSID) or "", self.o.get(CONF_WIFI_MDP) or ""
        return {"ssid": ssid, "mot_de_passe": pwd, "qr": wifi_qr(ssid, pwd, self.o.get(CONF_WIFI_SECU))}

    def access_choices(self) -> list[dict]:
        out = []
        for eid in self.o.get(CONF_ACCES) or []:
            out.append({"entity_id": eid, "nom": self._access_name(eid),
                        "alarme": eid.startswith("alarm_control_panel.")})
        return out

    def _access_name(self, eid: str) -> str:
        """« Porte (Écurie) » : nom de l'entité, complété par sa pièce quand le nom ne la dit pas."""
        st = self.hass.states.get(eid)
        name = (st.name if st else None) or eid
        ent = er.async_get(self.hass).async_get(eid)
        area_id = ent.area_id if ent else None
        if ent and not area_id and ent.device_id:
            dev = dr.async_get(self.hass).async_get(ent.device_id)
            area_id = dev.area_id if dev else None
        area = ar.async_get(self.hass).async_get_area(area_id) if area_id else None
        if area and area.name.lower() not in name.lower():
            return f"{name} ({area.name})"
        return name

    def message(self, vid: str) -> str:
        v = self.eff(self._get(vid))
        names = {a["entity_id"]: a["nom"] for a in self.access_choices()}
        portes = [names.get(e, e) for e in v.get("acces") or []]
        w = self.wifi()
        return accueil_message(v, self.hass.config.location_name or "la maison", (w["ssid"], w["mot_de_passe"]),
                               self.o.get(CONF_CONSIGNES), portes, dt_util.now(), dt_util.get_default_time_zone())

    def _get(self, vid: str) -> dict:
        v = self.visites.get(str(vid or ""))
        if v is None:
            raise VisiteError("inconnue", "Visite introuvable (déjà supprimée ?).")
        return v

    # ───────── modifications ─────────
    def _taken_codes(self, exclude: str | None = None) -> set[str]:
        now = self.now()
        return {v["code"] for v in self._all(now).values()
                if v.get("code") and v["id"] != exclude and statut(v, now, self.avant, self.apres) != TERMINEE}

    def _apply(self, v: dict, data: dict, creating: bool) -> None:
        now = self.now()
        if "nom" in data or creating:
            nom = clean_name(data.get("nom"))
            if not nom:
                raise VisiteError("nom", "Indiquer le prénom ou le nom du visiteur.")
            v["nom"] = nom
        if "type" in data or creating:
            v["type"] = validate_type(data.get("type"))
        if self._apply_series(v, data, creating):
            self._apply_rest(v, data, creating)
            return
        debut = data.get("debut")
        if creating or "debut" in data:
            d = parse_dt(_to_iso(debut)) if debut else None
            if debut and d is None:
                raise VisiteError("debut", "Date d'arrivée invalide.")
            v["immediate"] = d is None
            d = d or now
            v["debut"] = dt_util.as_utc(d).isoformat()
        d = parse_dt(v["debut"])
        fin = data.get("fin")
        duree = data.get("duree")
        if fin:
            f = parse_dt(_to_iso(fin))
            if f is None:
                raise VisiteError("fin", "Date de départ invalide.")
            v["fin"] = dt_util.as_utc(f).isoformat()
        elif duree is not None:
            h = float(duree)
            if not 0 < h <= 24 * 60:
                raise VisiteError("duree", "Durée entre quelques minutes et 60 jours.")
            v["fin"] = (d + timedelta(hours=h)).isoformat()
        elif creating:
            h = float(self.o.get(CONF_DUREE_PASSAGE if v["type"] == PASSAGE else CONF_DUREE_SUR_PLACE) or 2)
            v["fin"] = (d + timedelta(hours=h)).isoformat()
        f = parse_dt(v["fin"])
        if f <= d:
            raise VisiteError("fin", "Le départ doit être après l'arrivée.")
        if f - d > timedelta(days=60):
            raise VisiteError("fin", "Une visite dure au plus 60 jours.")
        if creating and f <= now:
            raise VisiteError("fin", "Cette visite est déjà terminée (départ dans le passé).")
        self._apply_rest(v, data, creating)

    def _apply_series(self, v: dict, data: dict, creating: bool) -> bool:
        """Passages réguliers. Renvoie True si la visite est (ou reste) une série."""
        jours = data.get("repetition_jours")
        if jours is not None and not jours:  # liste vide : la série redevient une visite simple
            if v.pop("recurrence", None) is not None:
                v.pop("sauf", None)
                v.pop("serie_ok", None)
                if not (data.get("debut") and (data.get("fin") or data.get("duree"))):
                    raise VisiteError("fin", "Visite simple : indiquer l'arrivée et le départ.")
            return False
        if not v.get("recurrence") and jours is None:
            return False
        r = dict(v.get("recurrence") or {})
        for key, field in (("jours", "repetition_jours"), ("de", "heure_debut"), ("a", "heure_fin"),
                           ("toutes", "toutes_les")):
            if data.get(field) is not None:
                r[key] = data[field]
        try:
            v["recurrence"] = norm_recurrence(r)
        except ValueError as err:
            raise VisiteError("repetition", str(err)) from err
        tz, now = self.tz(), self.now()
        v["immediate"] = False
        if creating or data.get("debut") or not v.get("serie_ok"):
            d = _to_date(data.get("debut")) if data.get("debut") else None
            if data.get("debut") and d is None:
                raise VisiteError("debut", "Date de début invalide.")
            if d is None and not creating and parse_dt(v.get("debut")):
                d = parse_dt(v["debut"]).astimezone(tz).date()
            d = d or dt_util.as_local(now).date()
            v["debut"] = dt_util.as_utc(datetime.combine(d, datetime.min.time(), tzinfo=tz)).isoformat()
        first = parse_dt(v["debut"]).astimezone(tz).date()
        jusqu = data.get("jusqu_au") or data.get("fin")
        if jusqu or creating or not v.get("serie_ok"):
            last = _to_date(jusqu) if jusqu else None
            if jusqu and last is None:
                raise VisiteError("jusqu_au", "Date de fin des passages invalide.")
            last = last or first + timedelta(days=365)
            v["fin"] = dt_util.as_utc(datetime.combine(last + timedelta(days=1), datetime.min.time(),
                                                       tzinfo=tz)).isoformat()
        last = (parse_dt(v["fin"]) - timedelta(seconds=1)).astimezone(tz).date()
        if last < first:
            raise VisiteError("jusqu_au", "La fin des passages doit être après leur début.")
        if (last - first).days > SERIE_MAX_JOURS:
            raise VisiteError("jusqu_au", "Des passages réguliers sur 2 ans au plus.")
        v["serie_ok"] = True
        v.pop("terminee", None)
        v.pop("termine_le", None)
        if occurrence(v, now, tz, self.apres) is None:
            raise VisiteError("repetition", "Aucun passage à venir avec ces jours, horaires et dates.")
        return True

    def _apply_rest(self, v: dict, data: dict, creating: bool) -> None:
        if "plaques" in data or creating:
            v["plaques"] = plate_list(data.get("plaques"))
        for k, n in (("telephone", 30), ("note", 500)):
            if k in data or creating:
                v[k] = str(data.get(k) or "").strip()[:n]
        if "acces" in data or creating:
            allowed = set(self.o.get(CONF_ACCES) or [])
            acces = [e for e in (data.get("acces") or []) if e in allowed]
            refused = [e for e in (data.get("acces") or []) if e not in allowed]
            if refused:
                raise VisiteError("acces", "Accès non proposé aux visiteurs : " + ", ".join(refused)
                                  + " (options du module Visiteurs).")
            v["acces"] = acces
        if "alarme" in data or creating:
            v["alarme"] = bool(data.get("alarme"))
        want = data.get("code")
        if want is not None or creating:
            if want in (False, None, "", "aucun"):
                v.pop("code", None)
                v.pop("code_h", None)
            elif want is True or want == "nouveau" or (want == "garder" and not v.get("code")):
                c = generate_code(self._taken_codes(v.get("id")))
                v["code"], v["code_h"] = c, _hash(c)
            elif isinstance(want, str) and want.isdigit():
                if code_problem(want):
                    raise VisiteError("code", "Code refusé : 4 à 8 chiffres, pas trop simple.")
                if want in self._taken_codes(v.get("id")):
                    raise VisiteError("code", "Ce code est déjà donné à un autre visiteur.")
                v["code"], v["code_h"] = want, _hash(want)
        if v.get("code") and not v.get("acces") and not v.get("alarme"):
            raise VisiteError("acces", "Cocher au moins un accès pour le code visiteur (ou retirer le code).")

    async def add(self, data: dict, who: str) -> dict:
        vid = uuid.uuid4().hex[:10]
        v: dict[str, Any] = {"id": vid}
        self._apply(v, data, creating=True)
        v["creee_par"], v["creee_le"] = who, self.now().isoformat()
        self.visites[vid] = v
        await self._changed(v)
        return v

    async def update(self, vid: str, data: dict, who: str) -> dict:
        v = dict(self._get(vid))
        if v.get("recurrence") and data.get("repetition_jours") != []:
            self._apply(v, data, creating=False)  # une série terminée se rouvre en changeant ses dates
            v["modifiee_par"], v["modifiee_le"] = who, self.now().isoformat()
            self.visites[vid] = v
            await self._changed(v)
            return v
        if v.get("terminee") or self.status(v) == "terminee":
            # prolonger une visite terminée : la rouvrir
            if not (data.get("fin") or data.get("duree")):
                raise VisiteError("terminee", "Visite terminée : indiquer une nouvelle heure de départ pour la "
                                              "prolonger.")
            v.pop("terminee", None)
            v.pop("termine_le", None)
        self._apply(v, data, creating=False)
        if parse_dt(v["fin"]) <= self.now():
            raise VisiteError("fin", "Le départ est déjà passé : utiliser « Terminer ».")
        v["modifiee_par"], v["modifiee_le"] = who, self.now().isoformat()
        self.visites[vid] = v
        await self._changed(v)
        return v

    async def terminate(self, vid: str, who: str) -> dict:
        """Visite simple : terminée. Série : le passage en cours s'arrête (les suivants restent) ;
        hors passage, c'est toute la série qui s'arrête."""
        v = self._get(vid)
        if v.get("recurrence") and not v.get("terminee") and self.status(v) == EN_COURS:
            return await self.skip(vid, who)
        if not v.get("terminee"):
            v["terminee"], v["termine_le"], v["terminee_par"] = True, self.now().isoformat(), who
        await self._changed(v)
        return v

    async def skip(self, vid: str, who: str, day: Any = None) -> dict:
        """Série : un passage n'a pas lieu (ou s'arrête maintenant). Par défaut, le passage en cours ou le prochain."""
        v = self._get(vid)
        if not v.get("recurrence"):
            raise VisiteError("repetition", "Ce n'est pas une visite régulière.")
        if day is None:
            occ = occurrence(v, self.now(), self.tz(), self.apres)
            if occ is None:
                raise VisiteError("terminee", "Plus aucun passage prévu.")
            d = occ[0].astimezone(self.tz()).date()
        else:
            d = _to_date(day)
            if d is None:
                raise VisiteError("date", "Date invalide.")
        sauf = sorted(set(v.get("sauf") or []) | {d.isoformat()})
        v["sauf"] = sauf[-SAUF_MAX:]
        v["modifiee_par"], v["modifiee_le"] = who, self.now().isoformat()
        await self._changed(v)
        return v

    async def end_series_before(self, vid: str, day: date, who: str) -> None:
        """Agenda « ce passage et les suivants » : la série s'arrête la veille de `day`."""
        v = self._get(vid)
        first = parse_dt(v["debut"]).astimezone(self.tz()).date()
        if day <= first:
            await self.delete(vid, who)
            return
        v["fin"] = dt_util.as_utc(datetime.combine(day, datetime.min.time(), tzinfo=self.tz())).isoformat()
        v["modifiee_par"], v["modifiee_le"] = who, self.now().isoformat()
        await self._changed(v)

    async def delete(self, vid: str, who: str) -> None:
        self._get(vid)
        del self.visites[vid]
        if vid in self._actives:  # supprimée en cours : on annonce la fin
            ev = self._actives.pop(vid)
            self.hass.bus.async_fire(EVENT_FIN, self._event_data(ev))
            await self._on_end(ev, silent=True)
        await self._changed(None)

    async def mark_arrival(self, vid: str, source: str, announce: bool = True) -> bool:
        """Première arrivée constatée (plaque, code, bouton). Renvoie True si c'est la première."""
        v = self.visites.get(vid)
        if v is None or self.eff(v).get("arrivee"):
            return False
        v["arrivee"] = {"t": self.now().isoformat(), "source": source}
        self._store.async_delay_save(lambda: {"visites": self.visites}, 5)
        self._notify_listeners()
        if announce and self._prevenir() in ("tout", "arrivee_depart"):
            await self._send(f"👋 {v['nom']} est arrivé(e) ({source}).", self._niveau(), f"visiteur_{vid}")
        return True

    async def recognize_plate(self, reads: list[str]) -> dict | None:
        v = match_plate([str(r) for r in reads or []], self.current())
        if v:
            await self.mark_arrival(v["id"], "plaque " + ", ".join(v.get("plaques") or []))
        return v

    async def _changed(self, v: dict | None) -> None:
        self.hass.bus.async_fire(EVENT_CHANGE, {"id": v["id"] if v else None})
        await self._refresh(changed=True)

    # ───────── effets ─────────
    def _niveau(self) -> str:
        n = str(self.o.get(CONF_NIVEAU) or "alerte")
        return n if n in ("info", "alerte", "admin") else "alerte"

    def _prevenir(self) -> str:
        return str(self.o.get(CONF_PREVENIR) or "tout")

    async def _on_start(self, v: dict) -> None:
        if self._prevenir() == "tout":
            fin = parse_dt(v.get("fin"))
            jusqu = dt_util.as_local(fin).strftime("%d/%m %H:%M") if fin else "?"
            await self._send(f"🧳 Visite de {v['nom']} ({TYPE_LABELS.get(v.get('type'), '')}) jusqu'au {jusqu}."
                             + (" Code visiteur actif." if v.get("code") else ""), self._niveau(), f"visiteur_{v['id']}")
        light = self.o.get(CONF_LUMIERE)
        sun = self.hass.states.get("sun.sun")
        if light and sun is not None and sun.state == "below_horizon" and self.hass.states.get(light) is not None:
            st = self.hass.states.get(light)
            if st.state == "off":
                try:
                    await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": light},
                                                        blocking=True, context=Context())
                    self.hass.data.setdefault(DOMAIN, {})["lumiere_allumee"] = light
                except HomeAssistantError as err:
                    _LOGGER.warning("Lumière d'accueil non allumée : %s", err)

    async def _on_end(self, v: dict, silent: bool = False) -> None:
        if not silent and self._prevenir() in ("tout", "arrivee_depart"):
            await self._send(f"🚪 Fin de la visite de {v.get('nom')}." + (" Son code ne fonctionne plus."
                                                                           if v.get("code") else ""),
                             self._niveau(), f"visiteur_{v['id']}")

    async def _lights_off(self, _now: Any) -> None:
        light = self.hass.data.get(DOMAIN, {}).pop("lumiere_allumee", None)
        if light and self.hass.states.is_state(light, "on"):
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": light}, blocking=False)

    async def _send(self, message: str, niveau: str, tag: str) -> None:
        svc = str(self.o.get(CONF_NOTIFY) or "").strip()
        try:
            if svc.count(".") == 1:
                dom, name = svc.split(".")
                if self.hass.services.has_service(dom, name):
                    data = ({"titre": "Visiteurs", "message": message, "niveau": niveau, "tag": tag}
                            if dom == "script" else {"title": "Visiteurs", "message": message})
                    await self.hass.services.async_call(dom, name, data, blocking=False)
                    return
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Notification non envoyée : %s", message)

    # ───────── pour le module Codes d'accès (code_pin ≥ 1.1) ─────────
    def codes_actifs(self) -> list[dict]:
        """Codes visiteur valables maintenant : empreinte, accès autorisés, alarme permise ou non."""
        return [{"id": v["id"], "nom": v.get("nom"), "code_h": v.get("code_h"), "acces": list(v.get("acces") or []),
                 "alarme": bool(v.get("alarme")), "fin": v.get("fin")}
                for v in self.current() if v.get("code_h")]

    async def code_utilise(self, vid: str, action: str, entity_name: str) -> None:
        await self.mark_arrival(vid, "code", announce=False)
        v = self.visites.get(vid) or {}
        if self._prevenir() != "rien":  # chaque usage d'un code visiteur est signalé (choix de Richard)
            await self._send(f"🔑 {v.get('nom', 'Visiteur')} : {action.lower()} {entity_name}.", self._niveau(),
                             f"visiteur_code_{vid}")


def _to_date(value: Any) -> date | None:
    """Date seule : « 2027-06-30 », un datetime (sa date locale) ou une chaîne date-heure."""
    if isinstance(value, datetime):
        return dt_util.as_local(value).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    d = dt_util.parse_date(value.strip()[:10])
    if d is not None and len(value.strip()) <= 10:
        return d
    iso = _to_iso(value)
    return dt_util.as_local(datetime.fromisoformat(iso)).date() if iso else d


def _to_iso(value: Any) -> str | None:
    """Accepte un datetime, une chaîne ISO, ou « AAAA-MM-JJ HH:MM[:SS] » en heure locale."""
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=dt_util.get_default_time_zone())).isoformat()
    if not isinstance(value, str):
        return None
    d = dt_util.parse_datetime(value.strip().replace(" ", "T", 1) if " " in value.strip() else value.strip())
    if d is None:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt_util.get_default_time_zone())
    return d.isoformat()

