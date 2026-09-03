"""Tests der Anreicherungsstufe.

Der Kern ist Robustheit: die Anreicherung ist eine Zugabe und darf die
Zustellung unter keinen Umstaenden verhindern.
"""
from datetime import date

from filter_dedup.anreicherung import SCHLUESSEL, Anreicherung, sicher_ergaenzen
from gemeinsam import profil as pr
from gemeinsam.jobdetail import JobdetailError

PROFIL = pr.Profil(faehigkeiten={"Java": 5, "Spring": 6, "SQL": 2})

def job() -> dict:
    """Frische Anzeige je Test.

    `ergaenze` haengt den Zusatz an die uebergebene Anzeige - genau so
    braucht der Consumer es. Ein geteiltes Dict waere damit nach dem
    ersten Test verunreinigt.
    """
    return {
        "stellenangebotsTitel": "Java Entwickler (m/w/d)",
        "datumErsteVeroeffentlichung": date.today().isoformat(),
        "stellenlokationen": [{"adresse": {"ort": "Hamburg"}, "entfernung": 8.2}],
    }


class FakeArchiv:
    def __init__(self, details=None, schreibfehler=False):
        self.details = details or {}
        self.schreibfehler = schreibfehler
        self.gemerkt = []

    def detail(self, referenznummer):
        return self.details.get(referenznummer)

    def merke_detail(self, referenznummer, inhalt):
        if self.schreibfehler:
            raise RuntimeError("S3 nicht erreichbar")
        self.gemerkt.append(referenznummer)
        self.details[referenznummer] = inhalt


def test_bewertung_haengt_unter_eigenem_schluessel():
    anzeige = job()
    an = Anreicherung(FakeArchiv(), PROFIL, abruf=lambda r: {"stellenangebotsBeschreibung": "Java, Spring, SQL"})

    an.ergaenze(anzeige, "10001-1-S")

    assert anzeige[SCHLUESSEL]["stufe"].startswith(("A", "B"))
    assert set(anzeige[SCHLUESSEL]["treffer"]) == {"Java", "Spring", "SQL"}
    assert anzeige[SCHLUESSEL]["alter_tage"] == 0
    assert anzeige[SCHLUESSEL]["entfernung_km"] == 8.2


def test_die_anzeige_selbst_wird_nicht_angetastet():
    """Der Zusatz kommt daneben, nicht hinein."""
    anzeige = job()
    an = Anreicherung(FakeArchiv(), PROFIL, abruf=lambda r: {})

    an.ergaenze(anzeige, "10001-1-S")

    assert set(anzeige) - set(job()) == {SCHLUESSEL}
    assert anzeige["stellenangebotsTitel"] == job()["stellenangebotsTitel"]


def test_detail_wird_gemerkt_und_wiederverwendet():
    archiv = FakeArchiv()
    aufrufe = []

    def abruf(referenznummer):
        aufrufe.append(referenznummer)
        return {"stellenangebotsBeschreibung": "Java"}

    an = Anreicherung(archiv, PROFIL, abruf=abruf)
    an.ergaenze(job(), "10001-1-S")
    an.ergaenze(job(), "10001-1-S")

    assert aufrufe == ["10001-1-S"]
    assert archiv.gemerkt == ["10001-1-S"]


def test_ohne_profil_nur_alter_und_entfernung():
    an = Anreicherung(FakeArchiv(), None, abruf=lambda r: {})

    zusatz = an.ergaenze(job(), "10001-1-S")

    assert "stufe" not in zusatz
    assert zusatz["alter_tage"] == 0


def test_unerreichbare_detailansicht_bricht_nicht_ab():
    def abruf(referenznummer):
        raise JobdetailError("HTTP 500")

    an = Anreicherung(FakeArchiv(), PROFIL, abruf=abruf)
    zusatz = an.ergaenze(job(), "10001-1-S")

    # Ohne Text bleibt nur der Titel - zu wenig fuer ein Urteil.
    assert zusatz["stufe"].startswith("D")


def test_fehler_beim_merken_stoppt_die_anreicherung_nicht():
    archiv = FakeArchiv(schreibfehler=True)
    an = Anreicherung(archiv, PROFIL, abruf=lambda r: {"stellenangebotsBeschreibung": "Java, Spring, SQL"})

    zusatz = an.ergaenze(job(), "10001-1-S")

    assert zusatz["stufe"].startswith(("A", "B"))


def test_sicher_ergaenzen_faengt_alles_ab():
    """Eine Mail ohne Bewertung ist besser als keine Mail."""
    class Kaputt:
        def ergaenze(self, job, referenznummer):
            raise ValueError("irgendwas")

    anzeige = job()
    sicher_ergaenzen(Kaputt(), anzeige, "10001-1-S")

    assert SCHLUESSEL not in anzeige


def test_ohne_anreicherung_passiert_nichts():
    anzeige = job()
    sicher_ergaenzen(None, anzeige, "10001-1-S")

    assert anzeige == job()
