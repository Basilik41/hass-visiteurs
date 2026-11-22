"""Fonctions pures (sans Home Assistant) : créneaux, statuts, codes, plaques, Wi-Fi, message d'accueil."""
from __future__ import annotations

import re
import secrets
import unicodedata
from datetime import date, datetime, time, timedelta
from itertools import pairwise
from typing import Any

from .const import CODE_LEN, PASSAGE, SUR_PLACE, TYPES

# ───────── visites ─────────
PREVUE, EN_COURS, TERMINEE = "prevue", "en_cours", "terminee"
STATUT_LABELS = {PREVUE: "Prévue", EN_COURS: "En cours", TERMINEE: "Terminée"}


def parse_dt(value: Any) -> datetime | None:
    """ISO (avec fuseau) → datetime ; None si invalide. Une heure sans fuseau est refusée (ambiguë)."""
    if isinstance(value, datetime):
        return value if value.tzinfo else None
    if not isinstance(value, str) or not value:
        return None
    try:
        d = datetime.fromisoformat(value)
    except ValueError:
        return None
    return d if d.tzinfo else None


def window(v: dict, avant: int, apres: int) -> tuple[datetime, datetime] | None:
    """Créneau effectif d'une visite (marges comprises), ou None si les dates sont invalides."""
    d, f = parse_dt(v.get("debut")), parse_dt(v.get("fin"))
    if d is None or f is None or f <= d:
        return None
    if v.get("immediate"):
        avant = 0  # « là maintenant » : pas de marge avant (début = heure de saisie)
    return d - timedelta(minutes=avant), f + timedelta(minutes=apres)


def statut(v: dict, now: datetime, avant: int, apres: int) -> str:
    if v.get("terminee"):
        return TERMINEE
    w = window(v, avant, apres)
    if w is None or now >= w[1]:
        return TERMINEE
    return EN_COURS if now >= w[0] else PREVUE


def actives(visites: dict[str, dict], now: datetime, avant: int, apres: int) -> list[dict]:
    out = [v for v in visites.values() if statut(v, now, avant, apres) == EN_COURS]
    return sorted(out, key=lambda v: (v.get("debut") or "", v.get("nom") or ""))


def prochaines(visites: dict[str, dict], now: datetime, avant: int, apres: int) -> list[dict]:
    out = [v for v in visites.values() if statut(v, now, avant, apres) == PREVUE]
    return sorted(out, key=lambda v: v.get("debut") or "")


def next_boundary(visites: dict[str, dict], now: datetime, avant: int, apres: int) -> datetime | None:
    """Prochain instant où une visite commence ou se termine (pour se réveiller pile à l'heure)."""
    best: datetime | None = None
    for v in visites.values():
        if v.get("terminee"):
            continue
        w = window(v, avant, apres)
        if w is None:
            continue
        for t in w:
            if t > now and (best is None or t < best):
                best = t
    return best


def purge(visites: dict[str, dict], now: datetime, avant: int, apres: int, days: int, maxi: int) -> dict[str, dict]:
    """Retire les visites terminées depuis plus de `days` jours ; garde au plus `maxi` visites."""
    limit = now - timedelta(days=days)
    keep = {}
    for k, v in visites.items():
        w = window(v, avant, apres)
        end = parse_dt(v.get("termine_le")) or (w[1] if w else None)
        if statut(v, now, avant, apres) == TERMINEE and (end is None or end < limit):
            continue
        keep[k] = v
    if len(keep) > maxi:
        ordered = sorted(keep.items(), key=lambda kv: kv[1].get("debut") or "")
        keep = dict(ordered[-maxi:])
    return keep


# ───────── passages réguliers (série) ─────────
JOURS_CLES = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
JOURS_COURTS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
_RRULE_DAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
SERIE_MAX_JOURS = 731     # une série dure au plus 2 ans
SAUF_MAX = 60             # dates sautées gardées


def parse_hhmm(value: Any) -> time | None:
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0, tzinfo=None)
    m = re.fullmatch(r"\s*([01]?\d|2[0-3])\s*[:hH]\s*([0-5]\d)?(?::[0-5]\d)?\s*", str(value or ""))
    return time(int(m[1]), int(m[2] or 0)) if m else None


def parse_day(value: Any) -> int | None:
    """« mardi », « mar », « tu », 1 (lundi = 0) → numéro du jour."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 <= value <= 6 else None
    t = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower().strip(" .")
    if t.isdigit():
        return parse_day(int(t))
    for i, k in enumerate(JOURS_CLES):
        if t and (k.startswith(t) and len(t) >= 2 or t == _RRULE_DAYS[i].lower()):
            return i
    return None


def norm_recurrence(r: dict) -> dict:
    """{"jours": [...], "de": "08:00", "a": "12:00", "toutes": 1} vérifié ; ValueError(message) sinon."""
    jours = r.get("jours")
    if isinstance(jours, str):
        jours = re.split(r"[,;\s]+", jours)
    days = sorted({d for d in (parse_day(x) for x in (jours or [])) if d is not None})
    if not days:
        raise ValueError("Choisir au moins un jour pour les passages réguliers.")
    de, a = parse_hhmm(r.get("de")), parse_hhmm(r.get("a"))
    if de is None or a is None:
        raise ValueError("Indiquer l'heure de début et l'heure de fin des passages.")
    if de == a:
        raise ValueError("L'heure de fin doit être différente de l'heure de début.")
    try:
        toutes = int(r.get("toutes") or 1)
    except (TypeError, ValueError):
        toutes = 0
    if not 1 <= toutes <= 12:
        raise ValueError("Répétition : toutes les 1 à 12 semaines.")
    return {"jours": days, "de": de.strftime("%H:%M"), "a": a.strftime("%H:%M"), "toutes": toutes}


def _series_bounds(v: dict, tz) -> tuple[date, date] | None:
    d = parse_dt(v.get("serie_debut") or v.get("debut"))
    f = parse_dt(v.get("serie_fin") or v.get("fin"))
    if d is None or f is None or f <= d:
        return None
    # « fin » = minuit après le dernier jour
    return d.astimezone(tz).date(), (f - timedelta(seconds=1)).astimezone(tz).date()


def iter_occurrences(v: dict, tz, from_day: date, limit: int = 400):
    """Passages d'une série, dans l'ordre, à partir du jour `from_day` (dates sautées exclues)."""
    r = v.get("recurrence") or {}
    bounds = _series_bounds(v, tz)
    de, a = parse_hhmm(r.get("de")), parse_hhmm(r.get("a"))
    days = set(r.get("jours") or [])
    if bounds is None or de is None or a is None or not days:
        return
    first, last = bounds
    toutes = max(1, int(r.get("toutes") or 1))
    anchor = first - timedelta(days=first.weekday())
    sauf = set(v.get("sauf") or [])
    day = max(first, from_day)
    for _ in range(limit * 7 * toutes):
        if day > last or limit <= 0:
            return
        if day.weekday() in days and ((day - anchor).days // 7) % toutes == 0 and day.isoformat() not in sauf:
            s = datetime.combine(day, de, tzinfo=tz)
            e = datetime.combine(day + timedelta(days=1 if a <= de else 0), a, tzinfo=tz)
            limit -= 1
            yield s, e
        day += timedelta(days=1)


def occurrence(v: dict, now: datetime, tz, apres: int) -> tuple[datetime, datetime] | None:
    """Passage en cours ou prochain passage d'une série (None : plus aucun)."""
    from_day = (now.astimezone(tz) - timedelta(days=1)).date()
    for s, e in iter_occurrences(v, tz, from_day):
        if e + timedelta(minutes=apres) > now:
            return s, e
    return None


def effective(v: dict, now: datetime, tz, avant: int, apres: int) -> dict:
    """Une série vue comme une visite ordinaire : debut / fin = passage en cours ou prochain.
    Les autres visites sont rendues telles quelles."""
    if not v.get("recurrence") or v.get("terminee"):
        return v
    e = dict(v)
    e.setdefault("serie_debut", v.get("debut"))
    e.setdefault("serie_fin", v.get("fin"))
    occ = occurrence(e, now, tz, apres)
    if occ is None:  # série épuisée
        e["debut"], e["fin"] = e["serie_debut"], e["serie_fin"]
        e["terminee"] = True
        e.setdefault("termine_le", e["serie_fin"])
        return e
    s, f = occ
    e["debut"], e["fin"], e["immediate"] = s.isoformat(), f.isoformat(), False
    arr = parse_dt((v.get("arrivee") or {}).get("t"))
    if v.get("arrivee") and (arr is None or arr < s - timedelta(minutes=avant)):
        e.pop("arrivee")  # arrivée d'un passage précédent
    return e


def recurrence_text(r: dict) -> str:
    """« chaque mardi et jeudi de 8 h à 12 h », « un lundi sur deux de 14 h à 15 h 30 »."""
    days = [JOURS_CLES[d] for d in r.get("jours") or []]
    jours = days[0] if len(days) == 1 else ", ".join(days[:-1]) + " et " + days[-1] if days else "?"
    if len(days) == 7:
        jours = "tous les jours"
    toutes = int(r.get("toutes") or 1)

    def h(s: str) -> str:
        t = parse_hhmm(s)
        return f"{t.hour} h" + (f" {t.minute:02d}" if t.minute else "") if t else "?"
    quand = jours if len(days) == 7 else (f"chaque {jours}" if toutes == 1 else
                                         f"{jours} (une semaine sur {toutes})" if toutes > 2 else
                                         f"{jours} (une semaine sur deux)")
    if len(days) == 7 and toutes > 1:
        quand = f"tous les jours, une semaine sur {toutes}"
    return f"{quand} de {h(r.get('de'))} à {h(r.get('a'))}"


def rrule_text(r: dict, until: date | None = None) -> str:
    parts = ["FREQ=WEEKLY"]
    if int(r.get("toutes") or 1) > 1:
        parts.append(f"INTERVAL={int(r['toutes'])}")
    parts.append("BYDAY=" + ",".join(_RRULE_DAYS[d] for d in r.get("jours") or []))
    if until:
        parts.append(f"UNTIL={until.strftime('%Y%m%d')}")
    return ";".join(parts)


def parse_rrule(rule: str) -> tuple[list[int], int, date | None, int | None]:
    """« FREQ=WEEKLY;INTERVAL=2;BYDAY=TU,TH;UNTIL=20270630 » → (jours, toutes, jusqu'au, nombre)."""
    kv = dict(p.split("=", 1) for p in str(rule or "").upper().split(";") if "=" in p)
    if kv.get("FREQ") != "WEEKLY":
        raise ValueError("Seules les répétitions « chaque semaine » sont gérées pour les visiteurs.")
    days = [_RRULE_DAYS.index(re.sub(r"^[+-]?\d+", "", x)) for x in kv.get("BYDAY", "").split(",")
            if re.sub(r"^[+-]?\d+", "", x) in _RRULE_DAYS]
    until = None
    if kv.get("UNTIL"):
        m = re.match(r"(\d{4})(\d{2})(\d{2})", kv["UNTIL"])
        until = date(int(m[1]), int(m[2]), int(m[3])) if m else None
    count = int(kv["COUNT"]) if kv.get("COUNT", "").isdigit() else None
    return days, int(kv.get("INTERVAL") or 1), until, count


def validate_type(t: Any) -> str:
    return t if t in TYPES else SUR_PLACE


def clean_name(nom: Any) -> str:
    n = re.sub(r"\s+", " ", str(nom or "")).strip()
    return n[:60]


# ───────── codes visiteur ─────────
_COMMON = {"123456", "654321", "121212", "112233", "123123", "111222", "000000", "999999", "102030", "010203"}


def code_problem(pin: str) -> str | None:
    """Mêmes règles que les codes personnels (module Codes d'accès)."""
    if not isinstance(pin, str) or not pin.isascii() or not pin.isdigit():
        return "chiffres"
    if not 4 <= len(pin) <= 8:
        return "longueur"
    if len(set(pin)) <= 2 or pin in _COMMON:
        return "trop_simple"
    steps = {(int(b) - int(a)) % 10 for a, b in pairwise(pin)}
    if steps in ({1}, {9}):
        return "trop_simple"
    return None


def generate_code(taken: set[str], length: int = CODE_LEN) -> str:
    """Code aléatoire (secrets), différent des codes visiteur encore valables."""
    for _ in range(1000):
        c = "".join(secrets.choice("0123456789") for _ in range(length))
        if c not in taken and code_problem(c) is None:
            return c
    raise RuntimeError("Impossible de générer un code")


# ───────── plaques ─────────
_GROUPS = ["0OQD", "1IL", "8B", "2Z", "6G", "5S", "MNHK", "VWYU"]
_CANON = {ch: g[0] for g in _GROUPS for ch in g}


def norm_plate(p: Any) -> str:
    t = unicodedata.normalize("NFKD", str(p or "")).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]", "", t)


def fuzzy_plate(p: Any) -> str:
    """Forme « tolérante » : les caractères souvent confondus par la lecture de plaque sont rapprochés."""
    return "".join(_CANON.get(c, c) for c in norm_plate(p))


def plate_list(value: Any) -> list[str]:
    """« AB-123-CD, EF 456 GH » → ['AB-123-CD', 'EF-456-GH'] (forme affichée), doublons retirés."""
    raw = value if isinstance(value, list) else re.split(r"[,;\n]+", str(value or ""))
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        n = norm_plate(item)
        if len(n) < 4 or len(n) > 12 or n in seen:
            continue
        seen.add(n)
        m = re.fullmatch(r"([A-Z]{2})(\d{3})([A-Z]{2})", n)
        out.append(f"{m[1]}-{m[2]}-{m[3]}" if m else n)
    return out


def match_plate(reads: list[str], visits: list[dict]) -> dict | None:
    """Visite active dont une plaque correspond (tolérance OCR) à l'une des lectures."""
    wanted = {fuzzy_plate(r) for r in reads if len(norm_plate(r)) >= 5}
    if not wanted:
        return None
    for v in visits:
        for p in v.get("plaques") or []:
            if fuzzy_plate(p) in wanted:
                return v
    return None


# ───────── Wi-Fi et accueil ─────────
def _esc_wifi(s: str) -> str:
    return re.sub(r'([\\;,:"])', r"\\\1", s)


def wifi_qr(ssid: str | None, password: str | None, security: str | None) -> str | None:
    """Texte du QR code Wi-Fi standard (lu par l'appareil photo d'Android et d'iPhone)."""
    if not ssid:
        return None
    sec = (security or "WPA").upper()
    if sec not in ("WPA", "WEP", "NOPASS", "SAE"):
        sec = "WPA"
    if sec == "NOPASS" or not password:
        return f"WIFI:T:nopass;S:{_esc_wifi(ssid)};;"
    return f"WIFI:T:{sec};S:{_esc_wifi(ssid)};P:{_esc_wifi(password)};;"


_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
         "novembre", "décembre"]


def fr_datetime(d: datetime, ref: datetime | None = None) -> str:
    """« aujourd'hui à 14 h 30 », « demain à 9 h », « samedi 28 novembre à 18 h »."""
    h = f"{d.hour} h" + (f" {d.minute:02d}" if d.minute else "")
    if ref is not None:
        delta = (d.date() - ref.date()).days
        if delta == 0:
            return f"aujourd'hui à {h}"
        if delta == 1:
            return f"demain à {h}"
    return f"{_JOURS[d.weekday()]} {d.day} {_MOIS[d.month - 1]} à {h}"


def accueil_message(v: dict, site: str, wifi: tuple[str | None, str | None], consignes: str | None,
                    portes: list[str], now_local: datetime, tz) -> str:
    """Message à envoyer au visiteur (SMS, WhatsApp…). Ne contient le code que si un code est prévu."""
    d, f = parse_dt(v.get("debut")), parse_dt(v.get("fin"))
    lines = [f"Bonjour {v.get('nom') or ''},".replace(" ,", ","), ""]
    serie = v.get("recurrence")
    if serie:
        fin_serie = parse_dt(v.get("serie_fin"))
        jusqu = (f", jusqu'au {(fin_serie - timedelta(seconds=1)).astimezone(tz).strftime('%d/%m/%Y')}"
                 if fin_serie else "")
        lines.append(f"Vos passages ({site}) : {recurrence_text(serie)}{jusqu}.")
        if d and not v.get("terminee"):
            lines.append(f"Prochain passage : {fr_datetime(d.astimezone(tz), now_local)}.")
    elif d and f:
        lines.append(f"Votre visite ({site}) : du {fr_datetime(d.astimezone(tz), now_local)} "
                     f"au {fr_datetime(f.astimezone(tz), now_local)}.")
    if v.get("code"):
        quoi = ", ".join(portes) if portes else "les accès prévus"
        lines += ["", f"Votre code (tablette, bouton « Visiteur ») : {v['code']}", f"Il ouvre : {quoi}."]
        lines.append("Il ne fonctionne que pendant vos passages." if serie else
                     "Il ne fonctionne que pendant votre visite.")
    ssid, pwd = wifi
    if ssid:
        lines += ["", f"Wi-Fi : {ssid}" + (f" — mot de passe : {pwd}" if pwd else "")]
    if consignes and consignes.strip():
        lines += ["", consignes.strip()]
    return "\n".join(lines).strip()


def type_from_text(text: str | None, debut: datetime | None, fin: datetime | None) -> str:
    """Agenda : « passage » dans la description → passage ; sinon visite de plus de 6 h → reste sur place."""
    t = (text or "").lower()
    if "passage" in t:
        return PASSAGE
    if "sur place" in t or "dort" in t or "reste" in t:
        return SUR_PLACE
    if debut and fin and fin - debut <= timedelta(hours=6):
        return PASSAGE
    return SUR_PLACE


def in_night(local: datetime, start: str, end: str) -> bool:
    """Heure locale dans la plage de nuit (qui peut passer minuit)."""
    def hm(s: str) -> int:
        try:
            p = [int(x) for x in str(s).split(":")[:2]]
            return p[0] * 60 + (p[1] if len(p) > 1 else 0)
        except (ValueError, IndexError):
            return 0
    t, a, b = local.hour * 60 + local.minute, hm(start), hm(end)
    if a == b:
        return False
    return a <= t < b if a < b else (t >= a or t < b)


_WIFI_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # sans l, i, o, 0, 1 (faciles à confondre en dictant)


def generate_wifi_password(groups: int = 3, size: int = 4) -> str:
    """« k7mq-3hzt-p9wa » : 60 bits d'aléa, facile à dicter ou recopier."""
    return "-".join("".join(secrets.choice(_WIFI_ALPHABET) for _ in range(size)) for _ in range(groups))
