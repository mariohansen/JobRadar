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


# --- Passung, Alter, Entfernung ---------------------------------------

BEWERTET = {
    **ANZEIGE,
    "jobradar": {
        "stufe": "A – Volltreffer",
        "punkte": 88,
        "treffer": ["Java", "Spring"],
        "luecken": ["Kubernetes"],
        "alter_tage": 3,
        "entfernung_km": 12.5,
    },
}

SCHWACH = {
    **ANZEIGE,
    "referenznummer": "10001-2-S",
    "stellenangebotsTitel": "SAP Berater",
    "jobradar": {"stufe": "C – Randbereich", "punkte": 20, "treffer": [], "luecken": ["SAP"]},
}


def test_bewertung_steht_in_beiden_fassungen():
    text = mail.als_text([BEWERTET])
    html_text = mail.als_html([BEWERTET])

    for fassung in (text, html_text):
        assert "A – Volltreffer" in fassung
        assert "88 Punkte" in fassung
        assert "Java, Spring" in fassung
        assert "Kubernetes" in fassung


def test_alter_und_entfernung_stehen_dabei():
    text = mail.als_text([BEWERTET])

    assert "seit 3 Tagen online" in text
    # Dezimalkomma, die Mail ist auf Deutsch.
    assert "12,5 km" in text


def test_heute_veroeffentlicht_statt_null_tagen():
    frisch = {**ANZEIGE, "jobradar": {"alter_tage": 0}}

    assert "heute veroeffentlicht" in mail.als_text([frisch])


def test_beste_passung_steht_oben():
    """Wer zwoelf Treffer bekommt, liest die ersten drei."""
    text = mail.als_text([SCHWACH, BEWERTET])

    assert text.index("Data Engineer") < text.index("SAP Berater")


def test_unbewertete_anzeigen_sortieren_hinter_die_bewerteten():
    text = mail.als_text([ANZEIGE, SCHWACH])

    assert text.index("SAP Berater") < text.index("Data Engineer")


def test_mail_ohne_anreicherung_bleibt_wie_bisher():
    """Faellt die Anreicherung aus, darf die Mail nicht kaputtgehen."""
    text = mail.als_text([ANZEIGE])

    assert "Data Engineer (m/w/d)" in text
    assert "Punkte" not in text
    assert "<" not in text
