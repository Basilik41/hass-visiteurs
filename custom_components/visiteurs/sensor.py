"""« Visiteurs » : nombre de visites en cours, liste, plaques et prochaine arrivée."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import VisiteursEntity, brief
from .visites import parse_dt


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            add: AddConfigEntryEntitiesCallback) -> None:
    mgr = entry.runtime_data
    add([EnCours(mgr), Prochaine(mgr)])


class EnCours(VisiteursEntity, SensorEntity):
    _attr_icon = "mdi:account-multiple"
    _attr_native_unit_of_measurement = "visites"

    def __init__(self, mgr) -> None:
        super().__init__(mgr, "en_cours")

    @property
    def native_value(self) -> int:
        return len(self.mgr.current())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        cur = self.mgr.current()
        return {"visites": [brief(v) for v in cur], "noms": [v.get("nom") for v in cur],
                "plaques": self.mgr.plates(), "sur_lecteur": [v.get("nom") for v in cur if v["id"] in self.mgr.unifi]}


class Prochaine(VisiteursEntity, SensorEntity):
    _attr_icon = "mdi:account-arrow-right"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, mgr) -> None:
        super().__init__(mgr, "prochaine")

    @property
    def native_value(self) -> datetime | None:
        up = self.mgr.upcoming()
        return parse_dt(up[0]["debut"]) if up else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        up = self.mgr.upcoming()
        return {"nom": up[0].get("nom") if up else None, "a_venir": [brief(v) for v in up[:10]]}
