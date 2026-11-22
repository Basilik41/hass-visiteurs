"""Installation en un clic ; tous les réglages dans les options."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)

from .const import (
    CONF_ACCES,
    CONF_CONSIGNES,
    CONF_DUREE_PASSAGE,
    CONF_DUREE_SUR_PLACE,
    CONF_GESTION,
    CONF_LUMIERE,
    CONF_MARGE_APRES,
    CONF_MARGE_AVANT,
    CONF_NIVEAU,
    CONF_NOTIFY,
    CONF_NUIT_DEBUT,
    CONF_NUIT_FIN,
    CONF_PREVENIR,
    CONF_TABLET,
    CONF_WIFI_MDP,
    CONF_WIFI_SECU,
    CONF_WIFI_SSID,
    DEFAULT_TABLET,
    DEFAULTS,
    DOMAIN,
)

ACCESS_DOMAINS = ["cover", "lock", "alarm_control_panel", "switch", "button", "input_button", "valve"]


class VisiteursFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="Visiteurs", data={}, options=dict(DEFAULTS))
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return VisiteursOptions()


def _num(lo: float, hi: float, step: float, unit: str) -> NumberSelector:
    return NumberSelector(NumberSelectorConfig(min=lo, max=hi, step=step, unit_of_measurement=unit,
                                               mode=NumberSelectorMode.BOX))


class VisiteursOptions(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        o = {**DEFAULTS, **self.config_entry.options}
        if user_input is not None:
            # champs vidés : retirés (un TextSelector vide n'est pas renvoyé)
            data = {k: v for k, v in user_input.items() if v not in (None, "")}
            return self.async_create_entry(data=data)
        users = [u for u in await self.hass.auth.async_get_users() if not u.system_generated and u.is_active]
        user_opts = [SelectOptionDict(value=u.id, label=u.name or u.id) for u in users]

        def sv(key: str) -> dict | None:
            v = o.get(key)
            return {"suggested_value": v} if v not in (None, "", []) else None

        schema = vol.Schema({
            vol.Optional(CONF_ACCES, default=list(o.get(CONF_ACCES) or [])): EntitySelector(
                EntitySelectorConfig(domain=ACCESS_DOMAINS, multiple=True)),
            vol.Optional(CONF_WIFI_SSID, description=sv(CONF_WIFI_SSID)): TextSelector(),
            vol.Optional(CONF_WIFI_MDP, description=sv(CONF_WIFI_MDP)): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Required(CONF_WIFI_SECU, default=o.get(CONF_WIFI_SECU, "WPA")): SelectSelector(SelectSelectorConfig(
                options=[SelectOptionDict(value="WPA", label="WPA / WPA2"), SelectOptionDict(value="SAE", label="WPA3"),
                         SelectOptionDict(value="nopass", label="Ouvert (sans mot de passe)")],
                mode=SelectSelectorMode.DROPDOWN)),
            vol.Optional(CONF_CONSIGNES, description=sv(CONF_CONSIGNES)): TextSelector(
                TextSelectorConfig(multiline=True)),
            vol.Optional(CONF_LUMIERE, description=sv(CONF_LUMIERE)): EntitySelector(
                EntitySelectorConfig(domain=["light", "switch", "input_boolean"])),
            vol.Required(CONF_DUREE_PASSAGE, default=o[CONF_DUREE_PASSAGE]): _num(0.25, 24, 0.25, "h"),
            vol.Required(CONF_DUREE_SUR_PLACE, default=o[CONF_DUREE_SUR_PLACE]): _num(1, 720, 1, "h"),
            vol.Required(CONF_MARGE_AVANT, default=o[CONF_MARGE_AVANT]): _num(0, 240, 5, "min"),
            vol.Required(CONF_MARGE_APRES, default=o[CONF_MARGE_APRES]): _num(0, 240, 5, "min"),
            vol.Required(CONF_NUIT_DEBUT, default=o[CONF_NUIT_DEBUT]): TimeSelector(),
            vol.Required(CONF_NUIT_FIN, default=o[CONF_NUIT_FIN]): TimeSelector(),
            vol.Required(CONF_PREVENIR, default=o[CONF_PREVENIR]): SelectSelector(SelectSelectorConfig(
                options=[SelectOptionDict(value="tout", label="Début, arrivée, codes et fin de chaque visite"),
                         SelectOptionDict(value="arrivee_depart", label="Arrivée, codes et fin seulement"),
                         SelectOptionDict(value="codes", label="Seulement l'usage des codes visiteur"),
                         SelectOptionDict(value="rien", label="Rien")], mode=SelectSelectorMode.LIST)),
            vol.Required(CONF_NIVEAU, default=o[CONF_NIVEAU]): SelectSelector(SelectSelectorConfig(
                options=[SelectOptionDict(value="alerte", label="Richard et Julie (téléphones)"),
                         SelectOptionDict(value="admin", label="Administrateurs (téléphone)"),
                         SelectOptionDict(value="info", label="Discord seulement")],
                mode=SelectSelectorMode.LIST)),
            vol.Optional(CONF_NOTIFY, description=sv(CONF_NOTIFY)): TextSelector(),
            vol.Optional(CONF_GESTION, default=list(o.get(CONF_GESTION) or [])): SelectSelector(SelectSelectorConfig(
                options=user_opts, multiple=True, mode=SelectSelectorMode.DROPDOWN)),
            vol.Required(CONF_TABLET, default=o.get(CONF_TABLET, DEFAULT_TABLET)): TextSelector(),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
