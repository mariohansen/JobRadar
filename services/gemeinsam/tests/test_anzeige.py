"""Tests der Feldzuordnung, die mehr als ein Dienst braucht."""
from datetime import date

from gemeinsam import anzeige


def test_beschreibung_nimmt_den_aktuellen_feldnamen():
    detail = {"stellenangebotsBeschreibung": "Java, Spring, SQL"}

    assert anzeige.beschreibung(detail) == "Java, Spring, SQL"


def test_beschreibung_faellt_auf_den_alten_feldnamen_zurueck():
    """Die Schnittstelle hat `stellenbeschreibung` zu
    `stellenangebotsBeschreibung` umbenannt - der alte Name bleibt Rueckfall."""
    detail = {"stellenbeschreibung": "Kafka, Airflow"}

    assert anzeige.beschreibung(detail) == "Kafka, Airflow"


def test_beschreibung_ohne_detail_ist_leer():
    assert anzeige.beschreibung(None) == ""
    assert anzeige.beschreibung({}) == ""


def test_text_zieht_titel_beruf_und_beschreibung_zusammen():
    roh = {
        "stellenangebotsTitel": "Data Engineer",
        "hauptberuf": "Datenbankentwickler/in",
        "alleBerufe": ["Data Engineer"],
    }
    detail = {"stellenangebotsBeschreibung": "Wir suchen Erfahrung mit Airflow."}

    text = anzeige.text(roh, detail)

    assert "Data Engineer" in text
    assert "Datenbankentwickler/in" in text
    assert "Airflow" in text


def test_alter_tage_nimmt_die_erste_veroeffentlichung():
    heute = date(2026, 9, 3)
    roh = {"datumErsteVeroeffentlichung": "2026-08-24"}

    assert anzeige.alter_tage(roh, heute=heute) == 10
