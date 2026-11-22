"""Base commune des entités du module (une seule « appareil » : Visiteurs)."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, VERSION
from .manager import Visiteurs


class VisiteursEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, mgr: Visiteurs, key: str) -> None:
        self.mgr = mgr
        self._attr_unique_id = f"{mgr.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, mgr.entry.entry_id)}, name="Visiteurs",
                                            manufacturer="Basilik41", model="Visiteurs", sw_version=VERSION,
                                            entry_type=DeviceEntryType.SERVICE)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.mgr.async_add_listener(self.async_write_ha_state))


def brief(v: dict) -> dict:
    return {"id": v["id"], "nom": v.get("nom"), "type": v.get("type"), "debut": v.get("debut"), "fin": v.get("fin"),
            "plaques": v.get("plaques") or [], "arrive": bool(v.get("arrivee"))}
