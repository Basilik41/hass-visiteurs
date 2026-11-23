"""Constantes du module « Visiteurs »."""
from __future__ import annotations

DOMAIN = "visiteurs"
VERSION = "1.4.0"

CARD_URL = f"/{DOMAIN}/visiteurs-card.js"
STORE_KEY = f"{DOMAIN}.visites"
STORE_VERSION = 1

# types de visite
SUR_PLACE = "sur_place"     # reste sur place (dort, garde la maison…) : compte comme une présence
PASSAGE = "passage"         # artisan, livreur, voisin qui nourrit les animaux…
TYPES = (SUR_PLACE, PASSAGE)
TYPE_LABELS = {SUR_PLACE: "Reste sur place", PASSAGE: "Passage"}

# options
CONF_MARGE_AVANT = "marge_avant_min"
CONF_MARGE_APRES = "marge_apres_min"
CONF_DUREE_PASSAGE = "duree_passage_h"
CONF_DUREE_SUR_PLACE = "duree_sur_place_h"
CONF_WIFI_SSID = "wifi_ssid"
CONF_WIFI_MDP = "wifi_mot_de_passe"
CONF_WIFI_SECU = "wifi_securite"
CONF_CONSIGNES = "consignes"
CONF_NOTIFY = "notifier"
CONF_ACCES = "acces_proposes"
CONF_LUMIERE = "lumiere_accueil"
CONF_NUIT_DEBUT = "nuit_debut"
CONF_NUIT_FIN = "nuit_fin"
CONF_PREVENIR = "prevenir"            # tout | arrivee_depart | codes | rien
CONF_GESTION = "gestionnaires"         # comptes qui gèrent les visites (vide = toute la famille)
CONF_TABLET = "motif_tablette"
DEFAULT_TABLET = "TabDomo"
CONF_NIVEAU = "niveau"                # niveau de script.notifier : info | alerte | admin

# comportements lus par les automatisations (interrupteurs du module, réglables depuis le tableau de bord)
REGLES = {
    "regle_armement": ("Suspendre l'armement automatique pendant une visite", "mdi:shield-off-outline"),
    "regle_presence": ("Un invité sur place compte comme quelqu'un à la maison", "mdi:home-account"),
    "regle_passage_info": ("Passage de jour : personne détectée = simple info", "mdi:cctv"),
    "regle_alerte_nuit": ("La nuit, personne détectée = alerte même en visite", "mdi:weather-night"),
}

DEFAULTS = {
    "regle_armement": True,
    "regle_presence": True,
    "regle_passage_info": True,
    "regle_alerte_nuit": True,
    CONF_MARGE_AVANT: 30,
    CONF_MARGE_APRES: 30,
    CONF_DUREE_PASSAGE: 2,
    CONF_DUREE_SUR_PLACE: 24,
    CONF_WIFI_SECU: "WPA",
    CONF_NOTIFY: "script.notifier",
    CONF_NUIT_DEBUT: "22:00:00",
    CONF_NUIT_FIN: "06:00:00",
    CONF_PREVENIR: "tout",
    CONF_NIVEAU: "alerte",
}

CODE_LEN = 6
HISTORY_DAYS = 90
MAX_VISITES = 500
REFRESH_SECONDS = 60

EVENT_DEBUT = f"{DOMAIN}_debut"
EVENT_FIN = f"{DOMAIN}_fin"
EVENT_CHANGE = f"{DOMAIN}_modifie"

# fournisseur lu par le module « Codes d'accès » (code_pin ≥ 1.1)
CODE_PIN_PROVIDER = "code_pin_visiteurs"
