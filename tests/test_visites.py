"""Tests des fonctions pures (python -m pytest tests/test_visites.py)."""
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_pkg = types.ModuleType("visiteurs")  # paquet sans son __init__ (pas de Home Assistant ici)
_pkg.__path__ = [str(Path(__file__).parents[1] / "custom_components" / "visiteurs")]
sys.modules["visiteurs"] = _pkg

from visiteurs.visites import (  # noqa: E402
    EN_COURS,
    PREVUE,
    TERMINEE,
    accueil_message,
    actives,
    code_problem,
    fr_datetime,
    fuzzy_plate,
    generate_code,
    in_night,
    match_plate,
    next_boundary,
    parse_dt,
    plate_list,
    purge,
    statut,
    type_from_text,
    wifi_qr,
)

UTC = timezone.utc
T0 = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
PARIS = ZoneInfo("Europe/Paris")


def v(i, d_h, f_h, **kw):
    return {"id": i, "nom": i, "type": kw.pop("type", "sur_place"), "debut": (T0 + timedelta(hours=d_h)).isoformat(),
            "fin": (T0 + timedelta(hours=f_h)).isoformat(), **kw}


def test_parse_dt():
    assert parse_dt("2026-11-22T12:00:00+00:00") == T0
    assert parse_dt("2026-11-22T12:00:00") is None  # sans fuseau : refusé
    assert parse_dt("n'importe quoi") is None and parse_dt(None) is None and parse_dt(12) is None


def test_statut_et_marges():
    a = v("a", 1, 3)
    assert statut(a, T0, 30, 30) == PREVUE
    assert statut(a, T0 + timedelta(minutes=31), 30, 30) == EN_COURS        # marge avant
    assert statut(a, T0 + timedelta(hours=3, minutes=29), 30, 30) == EN_COURS  # marge après
    assert statut(a, T0 + timedelta(hours=3, minutes=30), 30, 30) == TERMINEE
    assert statut({**a, "terminee": True}, T0 + timedelta(hours=2), 30, 30) == TERMINEE
    assert statut({**a, "fin": a["debut"]}, T0, 0, 0) == TERMINEE           # dates incohérentes
    assert statut({**a, "fin": "x"}, T0, 0, 0) == TERMINEE
    imm = v("i", 0, 2, immediate=True)
    assert statut(imm, T0 - timedelta(minutes=10), 30, 30) == PREVUE         # pas de marge avant pour « maintenant »


def test_actives_et_reveil():
    vs = {"a": v("a", -1, 1), "b": v("b", 2, 4), "c": v("c", -5, -4), "d": v("d", -1, 5, terminee=True)}
    assert [x["id"] for x in actives(vs, T0, 0, 0)] == ["a"]
    assert next_boundary(vs, T0, 0, 0) == T0 + timedelta(hours=1)
    assert next_boundary(vs, T0 + timedelta(hours=1), 0, 0) == T0 + timedelta(hours=2)
    assert next_boundary({}, T0, 0, 0) is None


def test_purge():
    vs = {"vieux": v("vieux", -24 * 100, -24 * 99), "recent": v("recent", -48, -47), "futur": v("futur", 5, 6),
          "fini_tot": v("fini_tot", -24 * 100, 24, terminee=True, termine_le=(T0 - timedelta(days=95)).isoformat())}
    p = purge(vs, T0, 0, 0, 90, 500)
    assert set(p) == {"recent", "futur"}
    many = {str(i): v(str(i), i, i + 1) for i in range(10)}
    assert len(purge(many, T0, 0, 0, 90, 4)) == 4


def test_codes():
    for bad in ("123456", "111111", "121212", "987654", "12a456", "123", "123456789", "112211"):
        assert code_problem(bad), bad
    assert code_problem("482917") is None
    taken = set()
    for _ in range(200):
        c = generate_code(taken)
        assert len(c) == 6 and c not in taken and code_problem(c) is None
        taken.add(c)


def test_plaques():
    assert plate_list("ab 123 cd, AB-123-CD ; ef456gh\n x") == ["AB-123-CD", "EF-456-GH"]
    assert plate_list(["GB 1234 X"]) == ["GB1234X"]
    assert fuzzy_plate("AB-123-CD") == fuzzy_plate("A8-I23-C0")
    vs = [{"id": "m", "nom": "Marc", "plaques": ["EK-262-WQ"]}]
    assert match_plate(["EK262WO"], vs)["nom"] == "Marc"
    assert match_plate(["EK262"], vs) is None            # trop court / différent
    assert match_plate(["FZ433ZL"], vs) is None
    assert match_plate([], vs) is None and match_plate(["EK262WQ"], []) is None


def test_wifi_qr():
    assert wifi_qr("Invites", "abc;def", "WPA") == "WIFI:T:WPA;S:Invites;P:abc\\;def;;"
    assert wifi_qr("Mon:Wifi", "", "WPA") == "WIFI:T:nopass;S:Mon\\:Wifi;;"
    assert wifi_qr("", "x", "WPA") is None
    assert wifi_qr("a", "b", "bizarre").startswith("WIFI:T:WPA;")


def test_message_et_dates():
    now = datetime(2026, 11, 22, 10, 0, tzinfo=PARIS)
    assert fr_datetime(datetime(2026, 11, 22, 14, 30, tzinfo=PARIS), now) == "aujourd'hui à 14 h 30"
    assert fr_datetime(datetime(2026, 11, 23, 9, 0, tzinfo=PARIS), now) == "demain à 9 h"
    assert fr_datetime(datetime(2026, 11, 28, 18, 0, tzinfo=PARIS), now) == "samedi 28 novembre à 18 h"
    visit = {"nom": "Marc", "debut": "2026-11-22T13:00:00+00:00", "fin": "2026-11-23T08:00:00+00:00",
             "code": "482917"}
    msg = accueil_message(visit, "la Grange", ("Invites", "pass1234"), "Fermer le portail.", ["Porte écurie"], now,
                          PARIS)
    assert "Bonjour Marc," in msg and "482917" in msg and "Porte écurie" in msg and "pass1234" in msg
    assert "aujourd'hui à 14 h" in msg and "demain à 9 h" in msg and msg.endswith("Fermer le portail.")
    sans = accueil_message({**visit, "code": None}, "la Grange", (None, None), "", [], now, PARIS)
    assert "code" not in sans.lower() and "Wi-Fi" not in sans


def test_type_depuis_agenda():
    d = T0
    assert type_from_text("Passage plombier", d, d + timedelta(days=2)) == "passage"
    assert type_from_text("", d, d + timedelta(hours=2)) == "passage"
    assert type_from_text("", d, d + timedelta(hours=7)) == "sur_place"
    assert type_from_text("reste dormir", d, d + timedelta(hours=1)) == "sur_place"


def test_nuit():
    def at(h, m=0):
        return datetime(2026, 11, 22, h, m, tzinfo=PARIS)
    assert in_night(at(23), "22:00:00", "06:00:00") and in_night(at(2), "22:00", "06:00")
    assert not in_night(at(6), "22:00", "06:00") and not in_night(at(12), "22:00", "06:00")
    assert in_night(at(13), "12:00", "14:00") and not in_night(at(14), "12:00", "14:00")
    assert not in_night(at(1), "00:00", "00:00")


def test_mot_de_passe_wifi():
    import re
    from visiteurs.visites import generate_wifi_password
    seen = {generate_wifi_password() for _ in range(200)}
    assert len(seen) == 200
    assert all(re.fullmatch(r"[a-hjkmnp-z2-9]{4}-[a-hjkmnp-z2-9]{4}-[a-hjkmnp-z2-9]{4}", p) for p in seen)
