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
    CONF_CONSIGNES,
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
from .visites import parse_dt

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
    vol.Optional("acces"): vol.Any(None, vol.All(cv.ensure_list, [cv.entity_id])),
    vol.Optional("alarme"): cv.boolean,
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
        return user.id in allowed
    return user.is_admin or _person_name(hass, user.id) is not None


def who(hass: HomeAssistant, user: User | None) -> str:
    if user is None:
        return "Automatisation"
    return _person_name(hass, user.id) or user.name or "Compte inconnu"


def _clean(data: dict) -> dict:
    names = {str(f) for f in _FIELDS}
    return {k: v for k, v in data.items() if k in names and v is not None}


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
    for cmd in (ws_info, ws_ajouter, ws_modifier, ws_terminer, ws_supprimer, ws_message):
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
        "nuit": m.is_night(), "maintenant": dt_util.utcnow().isoformat(),
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


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/message", vol.Required("visite"): _ID})
@websocket_api.async_response
@_handler(manage=True)
async def ws_message(hass: HomeAssistant, conn: websocket_api.ActiveConnection, msg: dict, m: Visiteurs) -> dict:
    return {"message": m.message(msg["visite"])}

