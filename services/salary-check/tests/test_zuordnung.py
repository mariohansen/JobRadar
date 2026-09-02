"""Tests der Zuordnung von Stellentiteln zu KldB-Schluesseln."""
from salary_check.zuordnung import kldb_aus_titel, niveau_aus_titel


def test_senior_gilt_als_experte():
    assert niveau_aus_titel("Senior Data Engineer (m/w/d)") == "4"


def test_lead_gilt_als_experte():
    assert niveau_aus_titel("Lead Software Engineer") == "4"


def test_junior_gilt_als_fachkraft():
    assert niveau_aus_titel("Junior Entwickler") == "2"


def test_ohne_hinweis_gilt_spezialist():
    assert niveau_aus_titel("Data Engineer") == "3"


def test_entwicklung_landet_in_der_softwaregruppe():
    assert kldb_aus_titel("Data Engineer") == "43413"


def test_beratungsbegriff_wechselt_die_gruppe():
    assert kldb_aus_titel("SAP Consultant") == "43213"


def test_kombination_aus_gruppe_und_niveau():
    assert kldb_aus_titel("Senior SAP Berater") == "43214"
