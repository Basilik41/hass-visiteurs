"""Interrupteurs de comportement, lus par les automatisations (armement, présence, alertes caméra)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import REGLES
from .entity import VisiteursEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            add: AddConfigEntryEntitiesCallback) -> None:
    mgr = entry.runtime_data
    add([Regle(mgr, key, icon) for key, (_label, icon) in REGLES.items()])


class Regle(VisiteursEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, mgr, key: str, icon: str) -> None:
        super().__init__(mgr, key)
        self.key = key
        self._attr_icon = icon

    @property
    def is_on(self) -> bool:
        return bool(self.mgr.o.get(self.key, True))

    async def _check(self) -> None:
        """Réglages de sécurité : administrateurs ou automatisations seulement (masquer ne protège pas)."""
        ctx = self._context
        if ctx and ctx.user_id:
            user = await self.hass.auth.async_get_user(ctx.user_id)
            if user is None or not user.is_admin:
                raise Unauthorized(context=ctx)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._check()
        await self.mgr.apply_settings({self.key: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._check()
        await self.mgr.apply_settings({self.key: False})
