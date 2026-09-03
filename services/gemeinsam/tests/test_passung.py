"""Tests des Faehigkeitsverzeichnisses, des Profils und der Bewertung.

Es wird mit erfundenen Profilen gearbeitet - echte Unterlagen haben in
einer Testsuite nichts verloren.
"""
import json

import pytest

from gemeinsam import faehigkeiten as fk
from gemeinsam import passung
from gemeinsam import profil as pr

PROFIL = pr.Profil(
    faehigkeiten={"Java": 5, "Spring": 6, "SQL": 2, "Docker": 1},
    quellen=("Lebenslauf.pdf",),
)

# Fuer die Faelle, in denen es auf den Umfang ankommt: mit vier
# Faehigkeiten laesst sich eine breite Anzeige nicht abdecken.
PROFIL_BREIT = pr.Profil(
    faehigkeiten={
        "Java": 5, "Spring": 6, "SQL": 2, "Docker": 1,
        "JUnit": 1, "Maven": 1, "Git": 1, "Linux": 1, "Scrum": 1,
    },
    quellen=("Lebenslauf.pdf",),
)


# --- Verzeichnis ------------------------------------------------------


def test_begriffe_werden_unabhaengig_von_der_schreibweise_gefunden():
    gefunden = fk.finde("Erfahrung mit JAVA, Spring Boot und PostgreSQL")

    assert "Java" in gefunden
    assert "Spring" in gefunden
    assert "PostgreSQL" in gefunden


def test_java_schlaegt_nicht_bei_javascript_an():
    assert "Java" not in fk.finde("Wir suchen einen JavaScript-Entwickler")
    assert "JavaScript" in fk.finde("Wir suchen einen JavaScript-Entwickler")


def test_go_wird_nicht_aus_go_live_gelesen():
    """Sonst haette jede zweite Anzeige die Sprache Go im Anforderungsprofil."""
    assert "Go" not in fk.finde("Begleitung bis zum Go-Live des Systems")
    assert "Go" not in fk.finde("wir go to market")
    assert "Go" in fk.finde("Backend in Go und Rust")


def test_haeufigkeiten_zaehlt_jede_nennung():
    zaehlung = fk.haeufigkeiten("Java, Java und nochmal Java. Dazu Python.")

    assert zaehlung["Java"] == 3
    assert zaehlung["Python"] == 1


def test_nach_kategorie_gruppiert_in_katalogreihenfolge():
    gruppen = fk.nach_kategorie(["Docker", "Java", "Python"])

    assert gruppen[fk.SPRACHEN] == ["Java", "Python"]
    assert gruppen[fk.CLOUD] == ["Docker"]


# --- Profil -----------------------------------------------------------


def test_schwerpunkt_ab_mehrfacher_nennung():
    assert PROFIL.kern == {"Java", "Spring"}
    assert PROFIL.alle == {"Java", "Spring", "SQL", "Docker"}


def test_eigene_eintragung_zaehlt_als_schwerpunkt():
    """Wer selbst nachtraegt, meint es - anders als eine Randnotiz."""
    ergaenzt = pr.Profil(faehigkeiten={"Java": 1}, eigene=("Terraform",))

    assert "Terraform" in ergaenzt.kern
    assert "Java" not in ergaenzt.kern


def test_ausgeschlossenes_verschwindet_aus_beiden_mengen():
    bereinigt = pr.Profil(
        faehigkeiten={"Java": 5, "Oracle": 4}, ausgeschlossen=("Oracle",)
    )

    assert bereinigt.alle == {"Java"}
    assert bereinigt.kern == {"Java"}


def test_profil_ueberlebt_speichern_und_laden(tmp_path):
    ziel = tmp_path / "profil.json"
    quelle = pr.Profil(
        faehigkeiten={"Java": 5}, eigene=("AWS",), ausgeschlossen=("Oracle",)
    )

    pr.speichere(quelle, ziel)
    zurueck = pr.lade(ziel)

    assert zurueck.faehigkeiten == {"Java": 5}
    assert zurueck.eigene == ("AWS",)
    assert zurueck.ausgeschlossen == ("Oracle",)


def test_gespeichertes_profil_ist_von_hand_lesbar(tmp_path):
    ziel = tmp_path / "profil.json"

    pr.speichere(pr.Profil(faehigkeiten={"SQL": 2, "Java": 9}), ziel)

    inhalt = json.loads(ziel.read_text(encoding="utf-8"))
    assert "hinweis" in inhalt
    # Absteigend, damit die Schwerpunkte oben stehen.
    assert list(inhalt["faehigkeiten"]) == ["Java", "SQL"]


def test_tippfehler_in_der_handpflege_wird_gemeldet(tmp_path, caplog):
    ziel = tmp_path / "profil.json"
    ziel.write_text(json.dumps({"eigene": ["Terrafrom"]}), encoding="utf-8")

    pr.lade(ziel)

    assert "Terrafrom" in caplog.text


def test_fehlendes_profil_nennt_den_befehl(tmp_path):
    with pytest.raises(pr.ProfilFehler) as fehler:
        pr.lade(tmp_path / "gibtsnicht.json")

    assert "tracker.main profil" in str(fehler.value)


def test_leeres_verzeichnis_wird_gemeldet(tmp_path):
    with pytest.raises(pr.ProfilFehler):
        pr.erstelle(tmp_path)


def test_scan_ohne_textebene_wird_gemeldet(tmp_path):
    """Ein eingescanntes Zeugnis liefert keinen Text - das muss auffallen."""
    (tmp_path / "lebenslauf.txt").write_text(
        "Java Entwickler mit Spring. " * 20, encoding="utf-8"
    )
    (tmp_path / "zeugnis.txt").write_text("   ", encoding="utf-8")

    erstellt, stumm = pr.erstelle(tmp_path)

    assert erstellt.quellen == ("lebenslauf.txt",)
    assert stumm == ["zeugnis.txt"]


# --- Bewertung --------------------------------------------------------


def test_volltreffer_braucht_deckung_und_substanz():
    """Stufe A gibt es erst, wenn die Anzeige auch etwas hergibt."""
    bewertung = passung.bewerte(
        PROFIL_BREIT,
        "Java Entwickler",
        "Spring Boot, SQL, Docker, JUnit, Maven, Git, Linux und Scrum.",
    )

    assert bewertung.stufe == passung.STUFE_A
    assert "Java" in bewertung.treffer


def test_duenne_anzeige_erreicht_die_spitze_nicht():
    """Drei Begriffe, alle getroffen - das ist keine Aussage, nur wenig Text."""
    bewertung = passung.bewerte(
        PROFIL, "Java Entwickler", "Wir setzen auf Spring Boot und SQL."
    )

    assert set(bewertung.treffer) == {"Java", "Spring", "SQL"}
    assert bewertung.luecken == ()
    assert bewertung.stufe == passung.STUFE_B


def test_randbereich_wenn_kaum_etwas_passt():
    bewertung = passung.bewerte(
        PROFIL, "SAP Berater", "Erfahrung mit Oracle, MongoDB und Kubernetes."
    )

    assert bewertung.stufe == passung.STUFE_C
    assert "Oracle" in bewertung.luecken


def test_titel_wiegt_schwerer_als_der_fliesstext():
    """Dieselben Begriffe, nur anders verteilt - das muss sich zeigen."""
    im_titel = passung.bewerte(PROFIL, "Java Entwickler", "Kubernetes, Oracle, Redis")
    im_text = passung.bewerte(PROFIL, "Entwickler", "Java, Kubernetes, Oracle, Redis")

    assert im_titel.punkte > im_text.punkte


def test_schwerpunkte_sind_in_der_trefferspalte_markiert():
    """Die Unterscheidung gehoert sichtbar in die Spalte, nicht in die Zahl."""
    bewertung = passung.bewerte(PROFIL, "Entwickler", "Java, SQL, Docker")

    assert "Java*" in bewertung.treffertext
    assert "SQL," in bewertung.treffertext or bewertung.treffertext.endswith("SQL")
    assert "SQL*" not in bewertung.treffertext


def test_die_punktzahl_haengt_nicht_am_schwerpunkt():
    """Sonst kaemen sehr verschiedene Anzeigen beide auf abgeschnittene 100."""
    schwerpunkt = pr.Profil(faehigkeiten={"Java": 9})
    randnotiz = pr.Profil(faehigkeiten={"Java": 1})
    anzeige = ("Entwickler", "Java, Kubernetes, Oracle")

    assert passung.bewerte(schwerpunkt, *anzeige).punkte == passung.bewerte(randnotiz, *anzeige).punkte


def test_volle_deckung_ergibt_keine_hundert_mehr():
    """Die Daempfung im Nenner deckelt, was eine kurze Anzeige erreichen kann."""
    bewertung = passung.bewerte(PROFIL, "Java Spring Entwickler", "Java, Spring, SQL")

    assert bewertung.luecken == ()
    assert bewertung.punkte < 100


def test_viele_treffer_schlagen_wenige_vollstaendige():
    """Der Grund fuer die Daempfung, an einem Beispiel.

    Vier von vier sagt weniger als acht von zehn - die zweite Anzeige
    nennt mehr und passt trotzdem weitgehend.
    """
    knapp = passung.bewerte(PROFIL_BREIT, "Entwickler", "Java, Spring, SQL, Docker")
    breit = passung.bewerte(
        PROFIL_BREIT,
        "Entwickler",
        "Java, Spring, SQL, Docker, JUnit, Maven, Git, Linux, Kafka, Oracle",
    )

    assert knapp.luecken == ()
    assert breit.luecken != ()
    assert breit.punkte > knapp.punkte


def test_breitere_deckung_schlaegt_schmalere():
    """Was der Bonus vorher verdeckt hat: zwei starke Anzeigen unterscheiden sich."""
    breit = passung.bewerte(
        PROFIL, "Java Entwickler", "Spring, SQL, Docker, Kubernetes"
    )
    schmal = passung.bewerte(
        PROFIL, "Java Entwickler", "Spring, Oracle, Kubernetes, Redis"
    )

    assert breit.punkte > schmal.punkte


def test_zu_wenig_angaben_wird_nicht_bewertet():
    """Eine Anzeige, die nur einen Begriff nennt, ergaebe glatte 100."""
    bewertung = passung.bewerte(PROFIL, "Java Entwickler", "")

    assert bewertung.stufe == passung.STUFE_D
    assert bewertung.brauchbar is False


def test_stufen_sortieren_in_der_richtigen_reihenfolge():
    stufen = [passung.STUFE_A, passung.STUFE_B, passung.STUFE_C, passung.STUFE_D]

    assert sorted(stufen) == stufen


def test_lange_listen_werden_gekuerzt():
    viele = tuple(f"Begriff {n}" for n in range(15))
    bewertung = passung.Bewertung(passung.STUFE_A, 80, viele, ())

    assert bewertung.treffertext.endswith("(+5)")
