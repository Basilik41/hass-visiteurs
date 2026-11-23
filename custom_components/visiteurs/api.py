"""Actions (services) et API de la carte. Droits : comptes de la famille (ou ceux choisis dans les options) ;
jamais une tablette murale ni un compte sans personne. Les automatisations (sans compte) peuvent tout faire."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
import voluptuous as vol
from homeassistant.auth.models import User
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ACCES,
    CONF_CONSIGNES,
    CONF_LUMIERE,
    CONF_MARGE_APRES,
    CONF_MARGE_AVANT,
    CONF_NIVEAU,
    CONF_NUIT_DEBUT,
    CONF_NUIT_FIN,
    CONF_PREVENIR,
    CONF_WIFI_MDP,
    CONF_WIFI_SECU,
    CONF_WIFI_SSID,
    REGLES,
    CONF_DUREE_PASSAGE,
    CONF_DUREE_SUR_PLACE,
    CONF_GESTION,
    CONF_TABLET,
    DEFAULT_TABLET,
    DOMAIN,
    TYPES,
    VERSION,
)
from .manager import VisiteError, Visiteurs
from .unifi import is_access_entity
from .visites import generate_wifi_password, parse_dt

_CODE = vol.Any(cv.boolean, vol.All(cv.string, vol.Match(r"^(\d{4,8}|nouveau|garder|aucun)$")))
_FIELDS = {
    vol.Optional("nom"): vol.All(cv.string, vol.Length(max=60)),
    vol.Optional("type"): vol.In(TYPES),
    vol.Optional("debut"): vol.Any(None, cv.string, cv.datetime),
    vol.Optional("fin"): vol.Any(None, cv.string, cv.datetime),
    vol.Optional("duree"): vol.Any(None, vol.All(vol.Coerce(float), vol.Range(min=0.05, max=1440))),
    vol.Optional("plaques"): vol.Any(None, cv.string, [cv.string]),
    vol.Optional("telephone"): vol.Any(None, vol.All(cv.string, vol.Length(max=30))),
    vol.Optional("note"): vol.Any(None, vol.All(cv.string, vol.Length(max=500))),
    vol.Optional("code"): _CODE,
    vol.Optional("acces"): vol.Any(None, vol.In(["tous"]), vol.All(cv.ensure_list, [cv.entity_id])),
    vol.Optional("notifications"): vol.Any(None, vol.In(["auto", "telephones", "journal", "aucune"])),
    vol.Optional("alarme"): cv.boolean,
    # passages réguliers : jours (lundi…dimanche), créneau, toutes les N semaines, jusqu'au (date)
    vol.Optional("repetition_jours"): vol.Any(None, vol.All(cv.ensure_list, [vol.Any(cv.string, vol.Coerce(int))])),
    vol.Optional("heure_debut"): vol.Any(None, cv.string),
    vol.Optional("heure_fin"): vol.Any(None, cv.string),
    vol.Optional("toutes_les"): vol.Any(None, vol.All(vol.Coerce(int), vol.Range(min=1, max=12))),
    vol.Optional("jusqu_au"): vol.Any(None, cv.string, cv.date, cv.datetime),
}
_ID = vol.All(cv.string, vol.Length(min=1, max=32))


def _mgr(hass: HomeAssistant) -> Visiteurs | None:
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        m = getattr(entry, "runtime_data", None)
        if isinstance(m, Visiteurs):
            return m
    return None


def _person_name(hass: HomeAssistant, user_id: str | None) -> str | None:
    for st in hass.states.async_all("person"):
        if user_id and st.attributes.get("user_id") == user_id:
            return st.name
    return None


def can_manage(hass: HomeAssistant, m: Visiteurs, user: User | None) -> bool:
    if user is None:
        return True  # automatisation, script lancé par HA
    motif = str(m.o.get(CONF_TABLET) or DEFAULT_TABLET).lower()
    if motif and motif in (user.name or "").lower():
        return False
    allowed = m.o.get(CONF_GESTION) or []
    if allowed:
        return user.id in allowed or _is_link(user)
    return user.is_admin or _is_link(user) or _person_name(hass, user.id) is not None


def _is_link(user: User) -> bool:
    """Compte de liaison entre Home Assistant (Remote HA) : la centrale ajoute ou termine des visites par lui."""
    return "liaison" in (user.name or "").lower()


def who(hass: HomeAssistant, user: User | None) -> str:
    if user is None:
        return "Automatisation"
    if _is_link(user):
        return "Centrale"
    return _person_name(hass, user.id) or user.name or "Compte inconnu"


def _clean(data: dict) -> dict:
    names = {str(f) for f in _FIELDS}
    out = {k: v for k, v in data.items() if k in names and v is not None}
    for k in ("heure_debut", "heure_fin", "jusqu_au"):  # sélecteurs heure / date : objets → texte
        if k in out and not isinstance(out[k], str):
            out[k] = out[k].isoformat()
    return out


# ───────── actions ─────────
@callback
def async_register_services(hass: HomeAssistant) -> None:
    async def guard(call: ServiceCall) -> tuple[Visiteurs, str]:
        m = _mgr(hass)
        if m is None:
            raise VisiteError("absent", "Module Visiteurs non configuré.")
        user = await hass.auth.async_get_user(call.context.user_id) if call.context.user_id else None
        if not can_manage(hass, m, user):
            raise Unauthorized(context=call.context)
        return m, who(hass, user)

    async def ajouter(call: ServiceCall) -> ServiceResponse:
        m, w = await guard(call)
        v = await m.add(_clean(dict(call.data)), w)
        return {"id": v["id"], "code": v.get("code"), "message": m.message(v["id"])}

    async def modifier(call: ServiceCall) -> ServiceResponse:
        m, w = await guard(call)
        v = await m.update(call.data["id"], _clean(dict(call.data)), w)
        return {"id": v["id"], "code": v.get("code")}

    async def terminer(call: ServiceCall) -> None:
        m, w = await guard(call)
        await m.terminate(call.data["id"], w)

    async def supprimer(call: ServiceCall) -> None:
        m, w = await guard(call)
        await m.delete(call.data["id"], w)

    async def sejour(call: ServiceCall) -> None:
        m, w = await guard(call)
        if call.data.get("retirer"):
            await m.remove_stays(call.data["id"], w, call.data.get("debut"))
        else:
            await m.add_stay(call.data["id"], w, call.data.get("fin"), call.data.get("debut"))

    async def sauter(call: ServiceCall) -> None:
        m, w = await guard(call)
        await m.skip(call.data["id"], w, call.data.get("date"))

    async def reconnaitre_plaque(call: ServiceCall) -> ServiceResponse:
        m, _ = await guard(call)
        reads = call.data.get("plaques") or []
        v = await m.recognize_plate(reads if isinstance(reads, list) else [reads])
        return {"trouve": bool(v), "id": v["id"] if v else None, "nom": v.get("nom") if v else None,
                "type": v.get("type") if v else None}

    async def arrivee(call: ServiceCall) -> None:
        m, w = await guard(call)
        await m.mark_arrival(call.data["id"], call.data.get("source") or w)

    add_fields = {k: v for k, v in _FIELDS.items() if str(k) != "nom"}
    hass.services.async_register(DOMAIN, "ajouter", ajouter, vol.Schema({
        vol.Required("nom"): vol.All(cv.string, vol.Length(min=1, max=60)), **add_fields}),
        supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "modifier", modifier, vol.Schema({vol.Required("id"): _ID, **_FIELDS}),
                                 supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "terminer", terminer, vol.Schema({vol.Required("id"): _ID}))
    hass.services.async_register(DOMAIN, "supprimer", supprimer, vol.Schema({vol.Required("id"): _ID}))
    hass.services.async_register(DOMAIN, "sejour", sejour, vol.Schema({
        vol.Required("id"): _ID, vol.Optional("debut"): vol.Any(None, cv.string, cv.datetime),
        vol.Optional("fin"): vol.Any(None, cv.string, cv.datetime), vol.Optional("retirer"): cv.boolean}))
    hass.services.async_register(DOMAIN, "sauter", sauter, vol.Schema({
        vol.Required("id"): _ID, vol.Optional("date"): vol.Any(cv.date, cv.string)}))
    hass.services.async_register(DOMAIN, "arrivee", arrivee, vol.Schema({
        vol.Required("id"): _ID, vol.Optional("source"): vol.All(cv.string, vol.Length(max=60))}))
    hass.services.async_register(DOMAIN, "reconnaitre_plaque", reconnaitre_plaque, vol.Schema({
        vol.Required("plaques"): vol.Any(cv.string, [cv.string])}), supports_response=SupportsResponse.ONLY)


# ───────── API de la carte ─────────
def _handler(manage: bool = False) -> Callable:
    def deco(fn: Callable[..., Awaitable[dict | None]]) -> Callable[..., Awaitable[None]]:
        @wraps(fn)
        async def wrapper(hass: HomeAssistant, conn: websocket_api.ActiveConnection, msg: dict) -> None:
            m = _mgr(hass)
            if m is None:
                conn.send_error(msg["id"], "not_loaded", "Module Visiteurs non configuré")
                return
            if manage and not can_manage(hass, m, conn.user):
                conn.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "Réservé à la famille")
                return
            try:
                res = await fn(hass, conn, msg, m)
            except VisiteError as err:
                conn.send_result(msg["id"], {"ok": False, "erreur": err.code, "message": err.message})
                return
            conn.send_result(msg["id"], {"ok": True, **(res or {})})
        return wrapper
    return deco


@callback
def async_register_ws(hass: HomeAssistant) -> None:
    for cmd in (ws_info, ws_ajouter, ws_modifier, ws_terminer, ws_supprimer, ws_sauter, ws_sejour, ws_message,
                ws_reglages, ws_regler, ws_lecteurs):
        websocket_api.async_register_command(hass, cmd)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/info",
                                  vol.Optional("jours", default=30): vol.All(vol.Coerce(int), vol.Range(0, 90))})
@websocket_api.async_response
@_handler()
async def ws_info(hass: HomeAssistant, conn: websocket_api.ActiveConnection, msg: dict, m: Visiteurs) -> dict:
    manage = can_manage(hass, m, conn.user)
    limit = dt_util.utcnow().timestamp() - msg["jours"] * 86400
    rows = []
    for v in m.visites.values():
        v = m.eff(v)
        st = m.status(v)
        end = parse_dt(v.get("termine_le")) or parse_dt(v.get("fin"))
        if st == "terminee" and (not manage or end is None or end.timestamp() < limit):
            continue
        rows.append(m.public(v, manage))
    order = {"en_cours": 0, "prevue": 1, "terminee": 2}
    rows.sort(key=lambda r: (order[r["statut"]], r["debut"] if r["statut"] != "terminee" else "",
                             "" if r["statut"] != "terminee" else r["debut"]))
    done = [r for r in rows if r["statut"] == "terminee"][::-1]
    rows = [r for r in rows if r["statut"] != "terminee"] + done
    return {
        "version": VERSION, "gestion": manage, "site": hass.config.location_name, "visites": rows,
        "acces": m.access_choices() if manage else [], "wifi": m.wifi(), "consignes": m.o.get(CONF_CONSIGNES) or "",
        "durees": {"passage": m.o.get(CONF_DUREE_PASSAGE), "sur_place": m.o.get(CONF_DUREE_SUR_PLACE)},
        "nuit": m.is_night(), "maintenant": dt_util.utcnow().isoformat(), "admin": _is_admin(conn.user),
        "lecteurs": {"disponible": m.access.available, "erreur": m.access.last_error if manage else None},
    }


# « type » est déjà le nom de la commande de l'API : le type de visite y s'appelle « type_visite »
_WS_FIELDS = {vol.Optional("type_visite" if str(k) == "type" else str(k)): v for k, v in _FIELDS.items()}


def _ws_data(msg: dict) -> dict:
    data = {k: v for k, v in msg.items() if k not in ("type", "id")}
    if "type_visite" in data:
        data["type"] = data.pop("type_visite")
    return _clean(data)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/ajouter", **_WS_FIELDS})
@websocket_api.async_response
@_handler(manage=True)
async def ws_ajouter(hass: HomeAssistant, conn: websocket_api.ActiveConnection, msg: dict, m: Visiteurs) -> dict:
    v = await m.add(_ws_data(msg), who(hass, conn.user))
    return {"visite": m.public(v, True), "message": m.message(v["id"])}


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/modifier", vol.Required("visite"): _ID,
                                  **_WS_FIELDS})
@websocket_api.async_response
@_handler(manage=True)
async def ws_modifier(hass: HomeAssistant, conn: websocket_api.ActiveConnection, msg: dict, m: Visiteurs) -> dict:
    v = await m.update(msg["visite"], _ws_data(msg), who(hass, conn.user))
    return {"visite": m.public(v, True)}


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/terminer", vol.Required("visite"): _ID})
@websocket_api.async_response
@_handler(manage=True)
async def ws_terminer(hass: HomeAssistant, conn: websocket_api.ActiveConnection, msg: dict, m: Visiteurs) -> None:
    await m.terminate(msg["visite"], who(hass, conn.user))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/supprimer", vol.Required("visite"): _ID})
@websocket_api.async_response
@_handler(manage=True)
async def ws_supprimer(hass: HomeAssistant, conn: websocket_api.ActiveConnection, msg: dict, m: Visiteurs) -> None:
    await m.delete(msg["visite"], who(hass, conn.user))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/sauter", vol.Required("visite"): _ID,
                                  vol.Optional("date"): cv.string})
@websocket_api.async_response
@_handler(manage=True)
async def ws_sauter(hass: HomeAssistant, conn: websocket_api.ActiveConnection, msg: dict, m: Visiteurs) -> None:
    await m.skip(msg["visite"], who(hass, conn.user), msg.get("date"))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/sejour", vol.Required("visite"): _ID,
                                  vol.Optional("debut"): cv.string, vol.Optional("fin"): cv.string,
                                  vol.Optional("retirer"): cv.boolean})
@websocket_api.async_response
@_handler(manage=True)
async def ws_sejour(hass: HomeAssistant, conn: websocket_api.ActiveConnection, msg: dict, m: Visiteurs) -> dict:
    if msg.get("retirer"):
        v = await m.remove_stays(msg["visite"], who(hass, conn.user), msg.get("debut"))
    else:
        v = await m.add_stay(msg["visite"], who(hass, conn.user), msg.get("fin"), msg.get("debut"))
    return {"visite": m.public(v, True)}


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/message", vol.Required("visite"): _ID})
@websocket_api.async_response
@_handler(manage=True)
async def ws_message(hass: HomeAssistant, conn: websocket_api.ActiveConnection, msg: dict, m: Visiteurs) -> dict:
    return {"message": m.message(msg["visite"])}



# ───────── réglages (administrateurs) ─────────
def _is_admin(user: User | None) -> bool:
    return user is None or user.is_admin


_HHMM = vol.All(cv.string, vol.Match(r"^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$"))
REGLAGES = {
    vol.Optional(CONF_WIFI_SSID): vol.All(cv.string, vol.Length(max=32)),
    vol.Optional(CONF_WIFI_MDP): vol.All(cv.string, vol.Length(max=63)),
    vol.Optional(CONF_WIFI_SECU): vol.In(["WPA", "SAE", "nopass"]),
    vol.Optional("wifi_generer"): cv.boolean,
    vol.Optional(CONF_CONSIGNES): vol.All(cv.string, vol.Length(max=2000)),
    vol.Optional(CONF_ACCES): vol.All(cv.ensure_list, [cv.entity_id]),
    vol.Optional(CONF_LUMIERE): vol.Any("", cv.entity_id),
    vol.Optional(CONF_DUREE_PASSAGE): vol.All(vol.Coerce(float), vol.Range(min=0.25, max=24)),
    vol.Optional(CONF_DUREE_SUR_PLACE): vol.All(vol.Coerce(float), vol.Range(min=1, max=720)),
    vol.Optional(CONF_MARGE_AVANT): vol.All(vol.Coerce(int), vol.Range(min=0, max=240)),
    vol.Optional(CONF_MARGE_APRES): vol.All(vol.Coerce(int), vol.Range(min=0, max=240)),
    vol.Optional(CONF_NUIT_DEBUT): _HHMM,
    vol.Optional(CONF_NUIT_FIN): _HHMM,
    vol.Optional(CONF_PREVENIR): vol.In(["tout", "arrivee_depart", "codes", "rien"]),
    vol.Optional(CONF_NIVEAU): vol.In(["alerte", "admin", "info"]),
    **{vol.Optional(k): cv.boolean for k in REGLES},
}
_ACCESS_DOMAINS = ("cover", "lock", "alarm_control_panel")


def _reglages(hass: HomeAssistant, m: Visiteurs) -> dict:
    keys = [str(k) for k in REGLAGES if str(k) != "wifi_generer"]
    current = {k: m.o.get(k) for k in keys}
    chosen = set(m.o.get(CONF_ACCES) or [])
    cands = sorted({s.entity_id for s in hass.states.async_all(_ACCESS_DOMAINS)}
                   | {s.entity_id for s in hass.states.async_all("button") if is_access_entity(hass, s.entity_id)}
                   | chosen)
    lights = sorted({s.entity_id for s in hass.states.async_all("light")}
                    | ({m.o[CONF_LUMIERE]} if m.o.get(CONF_LUMIERE) else set()))
    return {
        "valeurs": current,
        "regles": {k: label for k, (label, _icon) in REGLES.items()},
        "acces_possibles": [{"entity_id": e, "nom": m._access_name(e), "alarme": e.startswith("alarm_control_panel."),
                             "lecteur": is_access_entity(hass, e)} for e in cands],
        "lumieres_possibles": [{"entity_id": e, "nom": m._access_name(e)} for e in lights],
    }


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/reglages"})
@websocket_api.async_response
@_handler()
async def ws_reglages(hass: HomeAssistant, conn: websocket_api.ActiveConnection, msg: dict, m: Visiteurs) -> dict:
    if not _is_admin(conn.user):
        raise VisiteError("admin", "Réservé aux administrateurs.")
    return _reglages(hass, m)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/regler", **REGLAGES})
@websocket_api.async_response
@_handler()
async def ws_regler(hass: HomeAssistant, conn: websocket_api.ActiveConnection, msg: dict, m: Visiteurs) -> dict:
    if not _is_admin(conn.user):
        raise VisiteError("admin", "Réservé aux administrateurs.")
    data = {k: v for k, v in msg.items() if k not in ("type", "id")}
    if data.pop("wifi_generer", False):
        data[CONF_WIFI_MDP] = generate_wifi_password()
    secu = data.get(CONF_WIFI_SECU, m.o.get(CONF_WIFI_SECU))
    pwd = data.get(CONF_WIFI_MDP, m.o.get(CONF_WIFI_MDP)) or ""
    if secu != "nopass" and pwd and not 8 <= len(pwd) <= 63:
        raise VisiteError("wifi", "Mot de passe Wi-Fi : 8 à 63 caractères.")
    bad = [e for e in data.get(CONF_ACCES, []) if hass.states.get(e) is None]
    if bad:
        raise VisiteError("acces", "Entité introuvable : " + ", ".join(bad))
    await m.apply_settings(data)
    return _reglages(hass, m)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/lecteurs"})
@websocket_api.async_response
@_handler()
async def ws_lecteurs(hass: HomeAssistant, conn: websocket_api.ActiveConnection, msg: dict, m: Visiteurs) -> dict:
    """Diagnostic UniFi Access (administrateurs) : connexion, droits sur les visiteurs, portes."""
    if not _is_admin(conn.user):
        raise VisiteError("admin", "Réservé aux administrateurs.")
    res = await m.access.check()
    res["visiteurs_crees"] = len(m.unifi)
    res["erreur"] = m.access.last_error
    return {"lecteurs": res}
