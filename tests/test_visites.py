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


# ───────── passages réguliers ─────────
from visiteurs.visites import (  # noqa: E402
    effective,
    iter_occurrences,
    norm_recurrence,
    occurrence,
    parse_day,
    parse_rrule,
    recurrence_text,
    rrule_text,
)


def _serie(jours=(1, 3), de="08:00", a="12:00", toutes=1, debut=(2026, 11, 23), fin=(2027, 1, 1), **kw):
    d = datetime(*debut, tzinfo=PARIS)
    f = datetime(*fin, tzinfo=PARIS)
    return {"id": "s1", "nom": "Maréchal", "type": "passage", "debut": d.isoformat(), "fin": f.isoformat(),
            "recurrence": norm_recurrence({"jours": list(jours), "de": de, "a": a, "toutes": toutes}), **kw}


def test_jours_et_regles():
    assert parse_day("Mardi") == 1 and parse_day("mar") == 1 and parse_day("me") == 2 and parse_day("TU") == 1
    assert parse_day("dimanche") == 6 and parse_day(0) == 0 and parse_day("x") is None and parse_day(True) is None
    r = norm_recurrence({"jours": "jeudi, mardi", "de": "8h", "a": "12:30", "toutes": "2"})
    assert r == {"jours": [1, 3], "de": "08:00", "a": "12:30", "toutes": 2}
    for bad in ({"jours": [], "de": "8:00", "a": "9:00"}, {"jours": ["lundi"], "de": "8:00", "a": "8:00"},
                {"jours": ["lundi"], "de": "25:00", "a": "9:00"}, {"jours": ["lundi"], "de": "8:00", "a": "9:00",
                                                                      "toutes": 13}):
        try:
            norm_recurrence(bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    assert recurrence_text(r) == "mardi et jeudi (une semaine sur deux) de 8 h à 12 h 30"
    assert recurrence_text({"jours": [0], "de": "14:00", "a": "15:00", "toutes": 1}) == "chaque lundi de 14 h à 15 h"
    assert rrule_text(r) == "FREQ=WEEKLY;INTERVAL=2;BYDAY=TU,TH"
    assert parse_rrule("FREQ=WEEKLY;INTERVAL=2;BYDAY=TU,TH;UNTIL=20270630T215959Z") == ([1, 3], 2,
                                                                                       datetime(2027, 6, 30).date(), None)


def test_occurrences_et_statut():
    v = _serie()  # mardi et jeudi 8 h – 12 h à partir du lundi 23/11/2026
    lundi = datetime(2026, 11, 23, 10, tzinfo=PARIS)
    s, e = occurrence(v, lundi, PARIS, 30)
    assert s == datetime(2026, 11, 24, 8, tzinfo=PARIS) and e == datetime(2026, 11, 24, 12, tzinfo=PARIS)
    ev = effective(v, lundi, PARIS, 30, 30)
    assert statut(ev, lundi, 30, 30) == PREVUE and ev["serie_debut"] == v["debut"]
    mardi = datetime(2026, 11, 24, 9, tzinfo=PARIS)
    ev = effective(v, mardi, PARIS, 30, 30)
    assert statut(ev, mardi, 30, 30) == EN_COURS
    assert effective(ev, mardi, PARIS, 30, 30)["debut"] == ev["debut"]  # idempotent
    # marge après : 12 h 20 encore en cours, 12 h 31 → prochain = jeudi
    assert statut(effective(v, mardi.replace(hour=12, minute=20), PARIS, 30, 30), mardi.replace(hour=12, minute=20),
                  30, 30) == EN_COURS
    t = mardi.replace(hour=12, minute=31)
    ev = effective(v, t, PARIS, 30, 30)
    assert statut(ev, t, 30, 30) == PREVUE and parse_dt(ev["debut"]) == datetime(2026, 11, 26, 8, tzinfo=PARIS)
    # liste : 12 passages mardi/jeudi jusqu'au 31/12
    occ = list(iter_occurrences(v, PARIS, datetime(2026, 11, 1).date()))
    assert len(occ) == 12 and occ[-1][0] == datetime(2026, 12, 31, 8, tzinfo=PARIS)
    # après la fin : série épuisée → terminée
    ev = effective(v, datetime(2027, 1, 2, tzinfo=PARIS), PARIS, 30, 30)
    assert ev["terminee"] and statut(ev, datetime(2027, 1, 2, tzinfo=PARIS), 30, 30) == TERMINEE


def test_une_semaine_sur_deux_sauts_nuit_et_heure_d_ete():
    v = _serie(jours=[0], toutes=2, debut=(2026, 11, 25))  # 1re semaine = celle du mercredi 25/11 → lundi 23 exclu
    occ = [s.date().isoformat() for s, _ in iter_occurrences(v, PARIS, datetime(2026, 11, 1).date(), limit=3)]
    assert occ == ["2026-12-07", "2026-12-21"]  # la série s'arrête le 31/12
    v = _serie(sauf=["2026-11-24"])
    s, _ = occurrence(v, datetime(2026, 11, 24, 9, tzinfo=PARIS), PARIS, 30)
    assert s.date().isoformat() == "2026-11-26"
    nuit = _serie(jours=[4], de="22:00", a="06:00")  # vendredi 22 h → samedi 6 h
    t = datetime(2026, 11, 28, 3, tzinfo=PARIS)
    ev = effective(nuit, t, PARIS, 0, 0)
    assert statut(ev, t, 0, 0) == EN_COURS and parse_dt(ev["fin"]) == datetime(2026, 11, 28, 6, tzinfo=PARIS)
    ete = _serie(jours=[6], de="10:00", a="11:00", debut=(2027, 3, 20), fin=(2027, 4, 5))
    occ = list(iter_occurrences(ete, PARIS, datetime(2027, 3, 1).date()))
    assert [s.utcoffset() for s, _ in occ] == [timedelta(hours=1), timedelta(hours=2), timedelta(hours=2)]
    assert all(s.hour == 10 for s, _ in occ)


def test_arrivee_par_passage_et_message():
    v = _serie(arrivee={"t": datetime(2026, 11, 24, 8, 5, tzinfo=PARIS).isoformat(), "source": "code"})
    assert effective(v, datetime(2026, 11, 24, 9, tzinfo=PARIS), PARIS, 30, 30).get("arrivee")
    assert not effective(v, datetime(2026, 11, 26, 9, tzinfo=PARIS), PARIS, 30, 30).get("arrivee")
    ev = effective({**v, "code": "583920"}, datetime(2026, 11, 23, 10, tzinfo=PARIS), PARIS, 30, 30)
    msg = accueil_message(ev, "la Grange", (None, None), None, ["Porte écurie"],
                          datetime(2026, 11, 23, 10, tzinfo=PARIS), PARIS)
    assert "Vos passages (la Grange) : chaque mardi et jeudi de 8 h à 12 h, jusqu'au 31/12/2026." in msg
    assert "Prochain passage : demain à 8 h." in msg and "pendant vos passages" in msg


def test_nuit_sur_place_dans_une_serie():
    # papa : tous les jours 17 h – 19 h ; le mercredi 25/11 il reste dormir jusqu'au jeudi 10 h
    papa = _serie(jours=range(7), de="17:00", a="19:00", sejours=[{
        "debut": datetime(2026, 11, 25, 17, tzinfo=PARIS).isoformat(),
        "fin": datetime(2026, 11, 26, 10, tzinfo=PARIS).isoformat()}])
    t = datetime(2026, 11, 25, 18, tzinfo=PARIS)
    ev = effective(papa, t, PARIS, 30, 30)
    assert ev["type"] == "sur_place" and ev["dort_ici"] and statut(ev, t, 30, 30) == EN_COURS
    assert parse_dt(ev["fin"]) == datetime(2026, 11, 26, 10, tzinfo=PARIS)
    assert effective(ev, t, PARIS, 30, 30)["type"] == "sur_place"  # idempotent
    t2 = datetime(2026, 11, 26, 3, tzinfo=PARIS)  # la nuit : toujours là
    assert statut(effective(papa, t2, PARIS, 30, 30), t2, 30, 30) == EN_COURS
    t3 = datetime(2026, 11, 26, 12, tzinfo=PARIS)  # le lendemain midi : prochain passage 17 h, de passage
    ev = effective(papa, t3, PARIS, 30, 30)
    assert ev["type"] == "passage" and not ev["dort_ici"] and statut(ev, t3, 30, 30) == PREVUE
    assert parse_dt(ev["debut"]) == datetime(2026, 11, 26, 17, tzinfo=PARIS)
    # nuit séparée du passage (passage 8 h – 9 h, nuit à 20 h) : deux visites distinctes
    sep = _serie(jours=[2], de="08:00", a="09:00", sejours=[{
        "debut": datetime(2026, 11, 25, 20, tzinfo=PARIS).isoformat(),
        "fin": datetime(2026, 11, 26, 9, tzinfo=PARIS).isoformat()}])
    t = datetime(2026, 11, 25, 12, tzinfo=PARIS)
    ev = effective(sep, t, PARIS, 30, 30)
    assert parse_dt(ev["debut"]) == datetime(2026, 11, 25, 20, tzinfo=PARIS) and ev["type"] == "sur_place"
    # une nuit après la fin de la série la garde vivante
    fin = _serie(jours=[0], fin=(2026, 11, 24), sejours=[{
        "debut": datetime(2026, 12, 1, 20, tzinfo=PARIS).isoformat(),
        "fin": datetime(2026, 12, 2, 9, tzinfo=PARIS).isoformat()}])
    ev = effective(fin, datetime(2026, 11, 28, tzinfo=PARIS), PARIS, 30, 30)
    assert not ev.get("terminee") and ev["type"] == "sur_place"
