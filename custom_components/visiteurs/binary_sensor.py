"""« Invités sur place » (compte comme une présence) et « Passage en cours » (artisan, livreur…)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change

from .entity import VisiteursEntity, brief


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            add: AddConfigEntryEntitiesCallback) -> None:
    mgr = entry.runtime_data
    add([SurPlace(mgr), Passage(mgr), Nuit(mgr)])


class SurPlace(VisiteursEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PRESENCE
    _attr_icon = "mdi:account-group"

    def __init__(self, mgr) -> None:
        super().__init__(mgr, "sur_place")

    @property
    def is_on(self) -> bool:
        return bool(self.mgr.sur_place())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        vs = self.mgr.sur_place()
        return {"noms": [v.get("nom") for v in vs], "visites": [brief(v) for v in vs]}


class Passage(VisiteursEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_icon = "mdi:account-clock"

    def __init__(self, mgr) -> None:
        super().__init__(mgr, "passage")

    @property
    def is_on(self) -> bool:
        return bool(self.mgr.passages())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        vs = self.mgr.passages()
        return {"noms": [v.get("nom") for v in vs], "visites": [brief(v) for v in vs]}


class Nuit(VisiteursEntity, BinarySensorEntity):
    """Plage de nuit des options : pendant la nuit, une personne détectée reste une alerte même en visite."""
    _attr_icon = "mdi:weather-night"
    _attr_entity_registry_visible_default = False

    def __init__(self, mgr) -> None:
        super().__init__(mgr, "nuit")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_track_time_change(self.hass, self._minute, second=0))

    @callback
    def _minute(self, _now: Any) -> None:
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        return self.mgr.is_night()
