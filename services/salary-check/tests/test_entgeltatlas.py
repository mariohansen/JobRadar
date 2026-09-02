"""Tests der Auswertung von Entgeltatlas-Antworten."""
from salary_check import entgeltatlas
from salary_check.entgeltatlas import REGION_HAMBURG, entgelt, waehle_gesamtwert


def datensatz(
    region_id=REGION_HAMBURG,
    branche=1,
    alter=1,
    geschlecht=1,
    betrag=6329,
    q25=5126,
    q75=7615,
    fallzahl=9318,
):
    return {
        "region": {"id": region_id, "bezeichnung": "Hamburg"},
        "branche": {"id": branche, "bezeichnung": "Gesamt"},
        "ageCategory": {"id": alter, "bezeichnung": "Gesamt"},
        "gender": {"id": geschlecht, "bezeichnung": "Gesamt"},
        "performanceLevel": {"id": 4, "bezeichnung": "Experte"},
        "entgelt": betrag,
        "entgeltQ25": q25,
        "entgeltQ75": q75,
        "besetzung": fallzahl,
        "kldb": "43414",
    }


def test_gesamtwert_wird_aus_vielen_kombinationen_herausgesucht():
    daten = [datensatz(branche=6), datensatz(geschlecht=2), datensatz()]

    treffer = waehle_gesamtwert(daten, REGION_HAMBURG)

    assert treffer is not None
    assert treffer["branche"]["id"] == 1


def test_andere_region_wird_nicht_verwechselt():
    assert waehle_gesamtwert([datensatz(region_id=29)], REGION_HAMBURG) is None


def test_werte_werden_uebernommen(monkeypatch):
    monkeypatch.setattr(entgeltatlas, "hole_rohdaten", lambda kldb: [datensatz()])

    wert = entgelt("43414")

    assert wert is not None
    assert (wert.median, wert.q25, wert.q75) == (6329, 5126, 7615)


def test_platzhalter_gilt_nicht_als_gehalt(monkeypatch):
    """Die Schnittstelle liefert -1, wenn keine Daten vorliegen."""
    monkeypatch.setattr(
        entgeltatlas,
        "hole_rohdaten",
        lambda kldb: [datensatz(betrag=-1, q25=-1, q75=-1)],
    )

    assert entgelt("43114") is None


def test_fehlendes_quartil_wird_zu_null(monkeypatch):
    """Ein einzelnes Quartil kann fehlen, obwohl der Median vorliegt."""
    monkeypatch.setattr(
        entgeltatlas,
        "hole_rohdaten",
        lambda kldb: [datensatz(q75=-2, fallzahl=-42)],
    )

    wert = entgelt("43214")

    assert wert is not None
    assert wert.median == 6329
    assert wert.q75 == 0
    assert wert.fallzahl == 0
