"""Tests der Entfernungsberechnung ohne Netz."""
from gemeinsam import entfernung as ef


def test_gleicher_ort_ist_null():
    assert ef.zwischen("Hamburg", "Hamburg") == 0.0


def test_postleitzahl_und_land_stoeren_nicht():
    assert ef.zwischen("Hamburg", "20095 Hamburg") == 0.0
    assert ef.zwischen("Hamburg", "Hamburg, Deutschland") == 0.0


def test_umland_liegt_im_suchradius():
    """Was der Poller im Umkreis von 30 km sucht, muss auch so ankommen."""
    assert ef.zwischen("Hamburg", "Norderstedt") < 30
    assert ef.zwischen("Hamburg", "Pinneberg") < 30


def test_entfernte_staedte_sind_weit_weg():
    berlin = ef.zwischen("Hamburg", "Berlin")
    muenchen = ef.zwischen("Hamburg", "München")

    assert 240 < berlin < 270
    assert muenchen > berlin


def test_kurzform_findet_die_lange_schreibweise():
    assert ef.zwischen("Hamburg", "Frankfurt") == ef.zwischen(
        "Hamburg", "Frankfurt am Main"
    )


def test_unbekannter_ort_ergibt_nichts():
    """Eine leere Zelle ist besser als eine erfundene Zahl."""
    assert ef.zwischen("Hamburg", "Kleinkleckersdorf") is None
    assert ef.zwischen("Hamburg", "EMEA") is None
    assert ef.zwischen("Hamburg", "") is None
    assert ef.zwischen("Hamburg", None) is None


def test_normalisieren_raeumt_zusaetze_weg():
    assert ef.normalisiere("22765 Hamburg, Deutschland") == "hamburg"
    assert ef.normalisiere("Raum München") == "münchen"
    assert ef.normalisiere("  Köln  ") == "köln"


def test_entfernung_ist_symmetrisch():
    assert ef.zwischen("Hamburg", "Bremen") == ef.zwischen("Bremen", "Hamburg")
