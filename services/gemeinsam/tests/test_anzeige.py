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


# --- Stellenlink ------------------------------------------------------


def test_bundesagentur_verlinkt_ihre_eigene_oberflaeche():
    job = {"referenznummer": "10001-1-S"}

    assert anzeige.stellenlink(job).endswith("/jobsuche/jobdetail/10001-1-S")


def test_alte_eintraege_ohne_quelle_gelten_als_bundesagentur():
    assert anzeige.quelle({"referenznummer": "10001-1-S"}) == "arbeitsagentur"


def test_externes_portal_verdraengt_die_jobboerse_nicht():
    """Die Seite der Bundesagentur zeigt den vollen Text - die bleibt."""
    job = {
        "referenznummer": "10001-1-S",
        "quelle": "arbeitsagentur",
        "externeURL": "https://firma.de/stelle",
    }

    assert "arbeitsagentur.de" in anzeige.stellenlink(job)


def test_fremde_quelle_verlinkt_ihre_eigene_adresse():
    """Eine Jobboerse-URL mit 'arbeitnow:...' im Pfad laeuft ins Leere."""
    job = {
        "referenznummer": "arbeitnow:fullstack-braunschweig-79481",
        "quelle": "arbeitnow",
        "externeURL": "https://www.arbeitnow.com/jobs/x",
    }

    link = anzeige.stellenlink(job)

    assert link == "https://www.arbeitnow.com/jobs/x"
    assert "arbeitsagentur.de" not in link


def test_referenznummer_darf_von_aussen_kommen():
    """Faellt das Archiv aus, ist sie das Einzige, was bleibt."""
    link = anzeige.stellenlink({}, None, "10001-9-S")

    assert link.endswith("10001-9-S")
