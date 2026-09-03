"""Tests der Archivauswertung und des Berichts."""
from datetime import date

from gemeinsam import profil as pr

from tracker import bericht, trend

PROFIL = pr.Profil(faehigkeiten={"Java": 5, "Spring": 6}, quellen=("Lebenslauf.pdf",))


def anzeige(titel, text="", tag=date(2026, 8, 1), referenz="10001-1-S"):
    return tag, {
        "referenznummer": referenz,
        "stellenangebotsTitel": titel,
        "hauptberuf": text,
    }


def test_jede_anzeige_zaehlt_einmal_je_begriff():
    """Zwoelfmal Java in einer Anzeige ist eine Anzeige, die Java verlangt."""
    bestand = [anzeige("Java Entwickler", "Java Java Java und Spring")]

    ergebnis = trend.werte_aus(bestand, PROFIL)

    assert ergebnis.anzeigen == 1
    assert ergebnis.nachfrage["Java"] == 1
    assert ergebnis.nachfrage["Spring"] == 1


def test_luecken_und_abgedecktes_werden_getrennt():
    bestand = [
        anzeige("Java Entwickler", "Java, Kafka", referenz="a"),
        anzeige("Data Engineer", "Kafka, Spark", referenz="b"),
    ]

    ergebnis = trend.werte_aus(bestand, PROFIL)

    assert dict(ergebnis.luecken) == {"Kafka": 2, "Spark": 1}
    assert dict(ergebnis.abgedeckt) == {"Java": 1}


def test_wichtigste_luecke_steht_oben_und_nennt_den_anteil():
    bestand = [
        anzeige("Entwickler", "Kafka", referenz="a"),
        anzeige("Entwickler", "Kafka", referenz="b"),
        anzeige("Entwickler", "Spark", referenz="c"),
        anzeige("Entwickler", "Java", referenz="d"),
    ]

    oben = trend.werte_aus(bestand, PROFIL).wichtigste_luecken()[0]

    assert oben[0] == "Kafka"
    assert oben[1] == 2
    assert oben[2] == 0.5


def test_ohne_profil_nur_marktzahlen():
    ergebnis = trend.werte_aus([anzeige("Java Entwickler", "Kafka")])

    assert ergebnis.nachfrage["Kafka"] == 1
    assert not ergebnis.luecken
    assert not ergebnis.stufen


def test_zeitraum_und_verlauf_folgen_dem_ablagedatum():
    bestand = [
        anzeige("Java", tag=date(2026, 7, 15), referenz="a"),
        anzeige("Kafka Engineer", tag=date(2026, 8, 20), referenz="b"),
    ]

    ergebnis = trend.werte_aus(bestand, PROFIL)

    assert ergebnis.von == date(2026, 7, 15)
    assert ergebnis.bis == date(2026, 8, 20)
    assert ergebnis.monate() == ["2026-07", "2026-08"]
    assert ergebnis.verlauf["2026-08"]["Kafka"] == 1


def test_anzeigentexte_fliessen_ein():
    bestand = [anzeige("Entwickler", referenz="a")]

    ohne = trend.werte_aus(bestand, PROFIL)
    mit = trend.werte_aus(
        bestand, PROFIL, detail_zu=lambda r: {"stellenangebotsBeschreibung": "Kafka, Spark"}
    )

    assert not ohne.nachfrage
    assert mit.nachfrage["Kafka"] == 1


def test_kleiner_bestand_gilt_als_nicht_aussagekraeftig():
    assert not trend.werte_aus([anzeige("Java")]).aussagekraeftig()


# --- Bericht ----------------------------------------------------------


def bestand(anzahl=12):
    return [
        anzeige("Data Engineer", "Kafka, Spark, Java", referenz=f"r{n}")
        for n in range(anzahl)
    ]


def test_bericht_ist_eine_geschlossene_seite():
    """Kein Nachladen: die Datei muss vom Dateisystem aus funktionieren."""
    seite = bericht.baue(trend.werte_aus(bestand(), PROFIL), PROFIL)

    assert seite.startswith("<!doctype html>")
    assert seite.rstrip().endswith("</html>")
    assert "<script" not in seite
    assert "http://" not in seite and "https://" not in seite


def test_bericht_ist_fuer_kleine_bildschirme_gebaut():
    seite = bericht.baue(trend.werte_aus(bestand(), PROFIL), PROFIL)

    assert "width=device-width" in seite
    assert "prefers-color-scheme" in seite


def test_bericht_nennt_luecken_und_staerken():
    seite = bericht.baue(trend.werte_aus(bestand(), PROFIL), PROFIL)

    assert "Was dir am häufigsten fehlt" in seite
    assert "Kafka" in seite
    assert "Was du abdeckst" in seite
    assert "Java" in seite


def test_bericht_ohne_profil_zeigt_nur_den_markt():
    seite = bericht.baue(trend.werte_aus(bestand()))

    assert "Am häufigsten verlangt" in seite
    assert "Was dir am häufigsten fehlt" not in seite


def test_duenne_datenlage_wird_benannt():
    seite = bericht.baue(trend.werte_aus(bestand(3), PROFIL), PROFIL)

    assert "keine Aussage über den Markt" in seite


def test_sonderzeichen_zerlegen_das_markup_nicht():
    mit_ampersand = [anzeige("Java & Spring <Entwickler>", "Kafka")]

    seite = bericht.baue(trend.werte_aus(mit_ampersand, PROFIL), PROFIL)

    assert "<Entwickler>" not in seite
    assert "&lt;Entwickler&gt;" in seite or "Entwickler" not in seite


def test_verlauf_braucht_zwei_monate():
    einmonatig = bericht.baue(trend.werte_aus(bestand(), PROFIL), PROFIL)

    assert "mindestens zwei Monate" in einmonatig
