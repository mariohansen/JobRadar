"""Tests des Mailaufbaus."""
from notifier import mail

ANZEIGE = {
    "stellenangebotsTitel": "Data Engineer (m/w/d)",
    "firma": "Beispiel & Partner GmbH",
    "referenznummer": "10001-1003552327-S",
    "datumErsteVeroeffentlichung": "2026-08-17",
    "stellenlokationen": [{"adresse": {"ort": "Hamburg"}}],
}


def test_betreff_nennt_anzahl_und_ort():
    assert mail.betreff([ANZEIGE]) == "JobRadar: 1 neuer Treffer (Hamburg)"


def test_betreff_im_plural():
    assert "2 neue Treffer" in mail.betreff([ANZEIGE, ANZEIGE])


def test_betreff_faellt_bei_mehreren_orten_zurueck():
    woanders = {**ANZEIGE, "stellenlokationen": [{"adresse": {"ort": "Lueneburg"}}]}

    assert "Raum Hamburg" in mail.betreff([ANZEIGE, woanders])


def test_betreff_bleibt_nuechtern():
    text = mail.betreff([ANZEIGE])

    assert "!" not in text
    assert text != text.upper()


def test_textfassung_enthaelt_die_kerndaten():
    text = mail.als_text([ANZEIGE])

    assert "Data Engineer (m/w/d)" in text
    assert "Beispiel & Partner GmbH" in text
    assert "10001-1003552327-S" in text


def test_htmlfassung_maskiert_sonderzeichen():
    html_text = mail.als_html([ANZEIGE])

    # Das Und-Zeichen aus dem Firmennamen darf das Markup nicht zerlegen.
    assert "Beispiel &amp; Partner GmbH" in html_text
    assert "<a href=" in html_text


def test_anzeige_ohne_ort_und_firma():
    mager = {"stellenangebotsTitel": "Entwickler", "referenznummer": "x"}

    assert "nicht angegeben" in mail.als_text([mager])
    assert "Arbeitgeber nicht genannt" in mail.als_text([mager])
