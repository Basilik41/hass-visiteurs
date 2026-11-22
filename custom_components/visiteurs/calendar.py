"""Agenda « Visiteurs » : les visites s'affichent dans l'agenda de HA, et on peut en ajouter depuis l'agenda.

Titre = nom du visiteur. Description : « passage » → passage ; sinon une visite de plus de 6 h « reste sur place ».
Passages réguliers : chaque passage est un événement de la série (répétition « chaque semaine » de l'agenda).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEntityFeature, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import TYPE_LABELS
from .entity import VisiteursEntity
from .manager import VisiteError
from .visites import iter_occurrences, parse_dt, parse_rrule, rrule_text, type_from_text


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            add: AddConfigEntryEntitiesCallback) -> None:
    add([Agenda(entry.runtime_data)])


def _as_dt(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt_util.get_default_time_zone())
    return datetime.combine(value, time.min, tzinfo=dt_util.get_default_time_zone())


class Agenda(VisiteursEntity, CalendarEntity):
    _attr_icon = "mdi:calendar-account"
    _attr_supported_features = (CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.DELETE_EVENT
                                | CalendarEntityFeature.UPDATE_EVENT)

    def __init__(self, mgr) -> None:
        super().__init__(mgr, "agenda")
        self._attr_name = None  # nom de l'appareil : calendar.visiteurs

    def _event(self, v: dict, occ: tuple[datetime, datetime] | None = None) -> CalendarEvent | None:
        if v.get("recurrence") and occ is None:
            v = self.mgr.eff(v)
            if v.get("terminee"):
                return None
            occ = (parse_dt(v["debut"]), parse_dt(v["fin"]))
        d, f = occ if occ else (parse_dt(v.get("debut")), parse_dt(v.get("fin")))
        if d is None or f is None or f <= d:
            return None
        if v.get("terminee") and parse_dt(v.get("termine_le")):
            f = max(d + timedelta(minutes=1), min(f, parse_dt(v["termine_le"])))
        desc = [TYPE_LABELS.get(v.get("type"), "")]
        if v.get("plaques"):
            desc.append("Véhicule : " + ", ".join(v["plaques"]))
        if v.get("a_un_code") or v.get("code"):
            desc.append("Code visiteur")
        if v.get("note"):
            desc.append(v["note"])
        if not v.get("recurrence"):
            return CalendarEvent(start=dt_util.as_local(d), end=dt_util.as_local(f),
                                 summary=v.get("nom") or "Visiteur", description="\n".join(x for x in desc if x),
                                 uid=v["id"])
        fin = parse_dt(v.get("serie_fin") or v.get("fin"))
        until = (fin - timedelta(seconds=1)).astimezone(dt_util.get_default_time_zone()).date() if fin else None
        return CalendarEvent(start=dt_util.as_local(d), end=dt_util.as_local(f), summary=v.get("nom") or "Visiteur",
                             description="\n".join(x for x in desc if x), uid=v["id"],
                             recurrence_id=dt_util.as_local(d).strftime("%Y%m%d"),
                             rrule=rrule_text(v["recurrence"], until))

    @property
    def event(self) -> CalendarEvent | None:
        cur = self.mgr.current() or self.mgr.upcoming()
        return self._event(cur[0]) if cur else None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime,
                               end_date: datetime) -> list[CalendarEvent]:
        out = []
        tz = dt_util.get_default_time_zone()
        for v in self.mgr.visites.values():
            if v.get("recurrence"):
                if v.get("terminee"):
                    continue
                for occ in iter_occurrences(v, tz, (start_date.astimezone(tz) - timedelta(days=1)).date()):
                    if occ[0] >= end_date:
                        break
                    ev = self._event(v, occ)
                    if ev and ev.end > start_date:
                        out.append(ev)
                continue
            ev = self._event(v)
            if ev and ev.end > start_date and ev.start < end_date:
                out.append(ev)
        return sorted(out, key=lambda e: e.start)

    def _data(self, event: dict[str, Any]) -> dict[str, Any]:
        start, end = event.get("dtstart"), event.get("dtend")
        if start is None or end is None:
            raise HomeAssistantError("Indiquer le début et la fin de la visite.")
        d, f = _as_dt(start), _as_dt(end)
        desc = event.get("description") or ""
        note = "" if desc.strip().lower() in ("passage", "sur place", "reste sur place", "reste") else desc
        data = {"nom": event.get("summary"), "debut": d, "fin": f, "type": type_from_text(desc, d, f), "note": note}
        if event.get("rrule"):
            try:
                jours, toutes, until, count = parse_rrule(event["rrule"])
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err
            if not jours:
                jours = [d.weekday()]
            if until is None and count:
                until = (d + timedelta(weeks=toutes * ((count - 1) // len(jours) + 1))).date()
            data = {"nom": data["nom"], "note": note, "type": data["type"], "debut": d.date().isoformat(),
                    "repetition_jours": jours, "heure_debut": d.strftime("%H:%M"), "heure_fin": f.strftime("%H:%M"),
                    "toutes_les": toutes}
            if until:
                data["jusqu_au"] = until.isoformat()
        return data

    async def async_create_event(self, **kwargs: Any) -> None:
        try:
            await self.mgr.add(self._data(kwargs), "Agenda")
        except VisiteError as err:
            raise HomeAssistantError(err.message) from err

    async def async_delete_event(self, uid: str, recurrence_id: str | None = None,
                                 recurrence_range: str | None = None) -> None:
        try:
            v = self.mgr.visites.get(uid) or {}
            day = _rid_date(recurrence_id)
            if v.get("recurrence") and day is not None:
                if recurrence_range == "THISANDFUTURE":
                    await self.mgr.end_series_before(uid, day, "Agenda")
                else:
                    await self.mgr.skip(uid, "Agenda", day.isoformat())
                return
            await self.mgr.delete(uid, "Agenda")
        except VisiteError as err:
            raise HomeAssistantError(err.message) from err

    async def async_update_event(self, uid: str, event: dict[str, Any], recurrence_id: str | None = None,
                                 recurrence_range: str | None = None) -> None:
        cur = self.mgr.visites.get(uid) or {}
        if cur.get("recurrence"):
            raise HomeAssistantError("Passages réguliers : les modifier depuis la carte Visiteurs (ou supprimer un "
                                     "passage ici).")
        data = self._data(event)
        data["type"] = cur.get("type", data["type"])  # le type choisi dans la carte n'est pas écrasé
        if self.mgr.status(cur) != "prevue":
            data.pop("debut")  # visite commencée : seul le départ peut bouger
        try:
            await self.mgr.update(uid, data, "Agenda")
        except VisiteError as err:
            raise HomeAssistantError(err.message) from err


def _rid_date(rid: str | None) -> date | None:
    """Identifiant d'un passage (« 20261125 » ou « 20261125T080000 ») → sa date."""
    if not rid or len(rid) < 8 or not rid[:8].isdigit():
        return None
    try:
        return date(int(rid[:4]), int(rid[4:6]), int(rid[6:8]))
    except ValueError:
        return None
