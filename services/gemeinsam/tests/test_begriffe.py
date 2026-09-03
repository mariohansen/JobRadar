"""Tests der Kandidatensuche fuer neue Fachbegriffe."""
from gemeinsam import begriffe as bg


def test_abkuerzungen_werden_gefunden():
    gefunden = bg.kandidaten("Erfahrung mit DB2, COBOL und JCL auf dem Mainframe.")

    assert {"DB2", "COBOL", "JCL"} <= gefunden


def test_binnenmajuskeln_werden_gefunden():
    gefunden = bg.kandidaten("Wir arbeiten mit GitOps und OpenTelemetry.")

    assert {"GitOps", "OpenTelemetry"} <= gefunden


def test_bekannte_begriffe_tauchen_nicht_auf():
    """Was das Verzeichnis kennt, ist keine Entdeckung."""
    gefunden = bg.kandidaten("Kubernetes, PostgreSQL und GitLab im Einsatz.")

    assert not {"Kubernetes", "PostgreSQL", "GitLab"} & gefunden


def test_rechtsformen_und_floskeln_fallen_weg():
    gefunden = bg.kandidaten(
        "Die Beispiel GmbH sucht (m/w/d) ab sofort. Wir bieten VWL und HVV."
    )

    assert not {"GmbH", "VWL", "HVV"} & gefunden


def test_versalien_ueberschriften_sind_kein_fachbegriff():
    """Anzeigen schreien ihre Zwischenueberschriften gern in Grossbuchstaben."""
    gefunden = bg.kandidaten("DEINE AUFGABEN BEI UNS UND WAS WIR DIR BIETEN")

    assert not {"DEINE", "UNS", "WIR", "WAS", "DIR"} & gefunden


def test_haelften_bekannter_begriffe_fallen_weg():
    """Das Verzeichnis kennt CI/CD als Ganzes - nicht als zwei Funde."""
    gefunden = bg.kandidaten("Wir setzen auf CI/CD mit modernen Werkzeugen.")

    assert not {"CI", "CD"} & gefunden


def test_gezaehlt_wird_je_text_nicht_je_nennung():
    gezaehlt = bg.zaehle(
        [
            "COBOL, COBOL und nochmals COBOL.",
            "Hier geht es um COBOL und DB2.",
            "Nichts Besonderes.",
        ]
    )

    assert gezaehlt["COBOL"] == 2
    assert gezaehlt["DB2"] == 1


def test_leerer_text_ergibt_nichts():
    assert bg.kandidaten("") == set()
    assert bg.zaehle([]) == {}
