"""Tests der Homeoffice-Erkennung."""
from gemeinsam import homeoffice as ho


def test_prozentzahl_der_schnittstelle():
    assert ho.aus_prozent(100) == "100 % remote"
    assert ho.aus_prozent(40) == "hybrid, 40 % Homeoffice"
    assert ho.aus_prozent(0) == ""
    assert ho.aus_prozent(None) == ""


def test_vollstaendig_remote_in_allen_schreibweisen():
    for text in (
        "100 % Homeoffice innerhalb Deutschlands",
        "100%ige Homeoffice Tätigkeit",
        "100% Remote-Arbeit mit flexiblen Arbeitszeiten",
        "Diese Position kann zu 100% aus dem Homeoffice ausgeübt werden",
        "Ortsunabhängig: Homeoffice oder an einem unserer Standorte",
        "Wir arbeiten vollständig remote",
    ):
        assert ho.aus_text(text) == "100 % remote", text


def test_tage_je_woche_werden_beziffert():
    assert ho.aus_text("2 Tage Homeoffice pro Woche") == "hybrid, 2 Tage/Woche"
    assert ho.aus_text("1 Tag Homeoffice pro Woche") == "hybrid, 1 Tag/Woche"


def test_hybrid_nur_im_zusammenhang_mit_arbeit():
    assert ho.aus_text("ein hybrides Arbeitsmodell") == "hybrid, Umfang offen"
    assert ho.aus_text("Hybrides arbeiten (mobil & im Büro)") == "hybrid, Umfang offen"
    # Sonst faengt die Suche jede Cloud-Architektur mit ein.
    assert ho.aus_text("Wir setzen auf eine hybride Cloud") == ""


def test_moeglich_ohne_umfang():
    for text in (
        "Mobiles Arbeiten nach Absprache",
        "Work-Life-Balance durch Home-Office-Option",
        "Home Office (teilweise)",
        "Möglichkeit auf mobiles Arbeiten und Homeoffice",
    ):
        assert ho.aus_text(text) == "möglich, Umfang offen", text


def test_vor_ort_nur_wenn_die_anzeige_es_sagt():
    assert ho.aus_text("Wir bieten keine Möglichkeit zum Homeoffice") == "vor Ort"
    assert ho.aus_text("Präsenzpflicht an allen Arbeitstagen") == "vor Ort"


def test_beilaeufiges_vor_ort_ist_keine_aussage():
    """Der haeufigste Fehlgriff: "vor Ort" steht in ganz anderem Zusammenhang."""
    assert ho.aus_text("Sportangebote direkt vor Ort") == ""
    assert ho.aus_text("Termine bei unseren Kunden vor Ort") == ""
    assert ho.aus_text("Kenntnisse im Videopräsenzunterricht") == ""


def test_ohne_jede_angabe_bleibt_es_leer():
    assert ho.bestimme({}, {}, "") == ""
    assert ho.bestimme({"stellenangebotsTitel": "x"}, {}, "Ein Text ohne Aussage") == ""


def test_rangfolge_zahl_vor_text_vor_jaNein():
    # Zahl schlaegt Text.
    assert ho.bestimme({"homeofficeprozent": 40}, {}, "100 % Homeoffice") == (
        "hybrid, 40 % Homeoffice"
    )
    # Text schlaegt NACH_VEREINBARUNG.
    assert ho.bestimme({"homeofficetyp": "NACH_VEREINBARUNG"}, {}, "100 % remote") == (
        "100 % remote"
    )
    # Ohne Text bleibt NACH_VEREINBARUNG.
    assert ho.bestimme({"homeofficetyp": "NACH_VEREINBARUNG"}, {}, "") == (
        "nach Vereinbarung"
    )


def test_nach_vereinbarung_gilt_nicht_als_remote():
    """ADR 0006: der Wert sagt nur, dass darueber zu reden ist."""
    assert "remote" not in ho.bestimme({"homeofficetyp": "NACH_VEREINBARUNG"}, {}, "")
