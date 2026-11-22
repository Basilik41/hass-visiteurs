"""Visiteurs : visites prévues ou immédiates, présence des invités, passages, codes visiteur, accueil (Wi-Fi)."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .api import async_register_services, async_register_ws
from .const import CARD_URL, DOMAIN, STORE_KEY, STORE_VERSION
from .manager import Visiteurs

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
CARD_PATH = Path(__file__).parent / "frontend" / "visiteurs-card.js"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.CALENDAR, Platform.SWITCH]

type VisiteursConfigEntry = ConfigEntry[Visiteurs]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_register_services(hass)
    async_register_ws(hass)
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(CARD_PATH), True)])
    return True


async def async_setup_entry(hass: HomeAssistant, entry: VisiteursConfigEntry) -> bool:
    await _register_card(hass)
    mgr = Visiteurs(hass, entry)
    await mgr.async_start()
    entry.runtime_data = mgr
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_options_changed))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VisiteursConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        await entry.runtime_data.async_stop()
    return ok


async def async_remove_entry(hass: HomeAssistant, entry: VisiteursConfigEntry) -> None:
    """Désinstallation : visites effacées, carte retirée des ressources."""
    await Store(hass, STORE_VERSION, STORE_KEY).async_remove()
    resources = getattr(hass.data.get(LOVELACE_DATA), "resources", None)
    if resources is not None and getattr(hass.data.get(LOVELACE_DATA), "resource_mode", None) == "storage":
        try:
            await resources.async_get_info()
            for r in list(resources.async_items()):
                if str(r.get("url", "")).split("?")[0] == CARD_URL:
                    await resources.async_delete_item(r["id"])
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Ressource de la carte non retirée")


async def _options_changed(hass: HomeAssistant, entry: VisiteursConfigEntry) -> None:
    mgr = getattr(entry, "runtime_data", None)
    if mgr is not None and mgr.quiet_update:  # déjà appliqué par le module lui-même
        mgr.quiet_update = False
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def _register_card(hass: HomeAssistant) -> None:
    """Déclare la carte comme ressource de tableau de bord (rechargée dès qu'elle change)."""
    url = f"{CARD_URL}?v={await hass.async_add_executor_job(_file_hash, CARD_PATH)}"
    lovelace = hass.data.get(LOVELACE_DATA)
    resources = getattr(lovelace, "resources", None)
    if lovelace is not None and lovelace.resource_mode == "storage" and resources is not None:
        try:
            await resources.async_get_info()
            mine = [r for r in resources.async_items() if str(r.get("url", "")).split("?")[0] == CARD_URL]
            if not mine:
                await resources.async_create_item({"res_type": "module", "url": url})
            else:
                if mine[0].get("url") != url:
                    await resources.async_update_item(mine[0]["id"], {"res_type": "module", "url": url})
                for extra in mine[1:]:
                    await resources.async_delete_item(extra["id"])
            return
        except Exception:
            _LOGGER.exception("Ressource de la carte non enregistrée ; repli sur le chargement direct")
    if hass.data.setdefault(DOMAIN, {}).get("js_added"):
        return
    try:
        frontend.add_extra_js_url(hass, url)
        hass.data[DOMAIN]["js_added"] = True
    except KeyError:
        _LOGGER.debug("Interface non chargée : carte non injectée")


def _file_hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:10]
    except OSError:
        return "0"
