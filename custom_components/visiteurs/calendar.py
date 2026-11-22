"""Agenda « Visiteurs » : les visites s'affichent dans l'agenda de HA, et on peut en ajouter depuis l'agenda.

Titre = nom du visiteur. Description : « passage » → passage ; sinon une visite de plus de 6 h « reste sur place ».
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
from .visites import parse_dt, type_from_text


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

    def _event(self, v: dict) -> CalendarEvent | None:
        d, f = parse_dt(v.get("debut")), parse_dt(v.get("fin"))
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
        return CalendarEvent(start=dt_util.as_local(d), end=dt_util.as_local(f), summary=v.get("nom") or "Visiteur",
                             description="\n".join(x for x in desc if x), uid=v["id"])

    @property
    def event(self) -> CalendarEvent | None:
        cur = self.mgr.current() or self.mgr.upcoming()
        return self._event(cur[0]) if cur else None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime,
                               end_date: datetime) -> list[CalendarEvent]:
        out = []
        for v in self.mgr.visites.values():
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
        return {"nom": event.get("summary"), "debut": d, "fin": f, "type": type_from_text(desc, d, f), "note": note}

    async def async_create_event(self, **kwargs: Any) -> None:
        try:
            await self.mgr.add(self._data(kwargs), "Agenda")
        except VisiteError as err:
            raise HomeAssistantError(err.message) from err

    async def async_delete_event(self, uid: str, recurrence_id: str | None = None,
                                 recurrence_range: str | None = None) -> None:
        try:
            await self.mgr.delete(uid, "Agenda")
        except VisiteError as err:
            raise HomeAssistantError(err.message) from err

    async def async_update_event(self, uid: str, event: dict[str, Any], recurrence_id: str | None = None,
                                 recurrence_range: str | None = None) -> None:
        data = self._data(event)
        cur = self.mgr.visites.get(uid) or {}
        data["type"] = cur.get("type", data["type"])  # le type choisi dans la carte n'est pas écrasé
        if self.mgr.status(cur) != "prevue":
            data.pop("debut")  # visite commencée : seul le départ peut bouger
        try:
            await self.mgr.update(uid, data, "Agenda")
        except VisiteError as err:
            raise HomeAssistantError(err.message) from err
