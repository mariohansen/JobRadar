"""Tests der Stellenquellen.

Geprueft wird die Uebersetzung ins gemeinsame Format - ohne Netzzugriff:
jede Quelle bekommt eine erfundene Antwort untergeschoben. Was die
Portale wirklich liefern, ist nicht Gegenstand einer Testsuite.
"""
import pytest

from poller import quellen
from poller.config import SearchConfig
from poller.quellen import arbeitnow, basis, jobicy, remoteok, remotive


def config(**abweichend):
    werte = dict(
        base_url="https://example.invalid",
        api_key="x",
        suchbegriffe=("Data Engineer",),
        ort="Hamburg",
        umkreis_km=30,
        veroeffentlicht_seit_tagen=0,
        seitengroesse=50,
        remote_bundesweit=True,
        remote_min_prozent=100,
        quellen=("arbeitnow",),
    )
    werte.update(abweichend)
    return SearchConfig(**werte)


# --- Verzeichnis ------------------------------------------------------


def test_jede_quelle_hat_ein_hole():
    for name, modul in quellen.VERZEICHNIS.items():
        assert callable(getattr(modul, "hole", None)), name


def test_unbekannte_quelle_wird_abgewiesen():
    with pytest.raises(quellen.UnbekannteQuelle) as fehler:
        quellen.pruefe(("arbeitnow", "linkedin"))

    assert "linkedin" in str(fehler.value)


def test_bekannte_quellen_kommen_durch():
    assert quellen.pruefe(("arbeitnow", "jobicy")) == ("arbeitnow", "jobicy")


def test_adzuna_meldet_sich_ohne_zugangsdaten_ab(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)

    assert quellen.ist_verfuegbar("adzuna") is False
    assert quellen.ist_verfuegbar("arbeitnow") is True


# --- Hilfsfunktionen --------------------------------------------------


def test_html_wird_zu_lesbarem_text():
    text = basis.text_aus_html("<p>Wir suchen <b>Python</b>.</p><ul><li>Kafka</li></ul>")

    assert "<" not in text
    assert "Python" in text and "Kafka" in text


def test_html_trennt_aufzaehlungen_statt_sie_zu_verkleben():
    """Sonst entstuende 'KafkaAWS' und die Begriffssuche fiele darauf herein."""
    text = basis.text_aus_html("<li>Kafka</li><li>AWS</li>")

    assert "KafkaAWS" not in text


def test_datum_versteht_zeitstempel_und_iso():
    assert basis.als_datum(1756684800) == "2025-09-01"
    assert basis.als_datum("2026-08-17") == "2026-08-17"
    assert basis.als_datum("2026-08-17T07:01:02.150") == "2026-08-17"
    assert basis.als_datum(None) == ""


def test_ort_wird_in_die_adressstruktur_uebersetzt():
    assert basis.lokationen(["20095 Hamburg"]) == [
        {"adresse": {"plz": "20095", "ort": "Hamburg"}}
    ]
    assert basis.lokationen(["Hamburg, Deutschland"]) == [
        {"adresse": {"plz": "", "ort": "Hamburg"}}
    ]
    assert basis.lokationen(["", None]) == []


def test_suchbegriff_trifft_wortweise():
    assert basis.passt_zum_begriff("Senior Data Platform Engineer", ("Data Engineer",))
    assert not basis.passt_zum_begriff("Vertriebsmitarbeiter", ("Data Engineer",))


def test_anzeige_ohne_titel_oder_kennung_wird_verworfen():
    assert basis.anzeige("q", "", "Titel", "Firma") is None
    assert basis.anzeige("q", "1", "", "Firma") is None


def test_anzeige_traegt_quelle_und_praefix():
    gebaut = basis.anzeige("arbeitnow", "abc", "Data Engineer", "Beispiel GmbH")

    assert gebaut["quelle"] == "arbeitnow"
    assert gebaut["referenznummer"] == "arbeitnow:abc"


# --- Arbeitnow --------------------------------------------------------


def _seitenweise(jobs):
    """Erste Seite mit Inhalt, danach leer - wie die echte Schnittstelle."""
    gelesen = {"seiten": 0}

    def antwort(url, kopfzeilen=None):
        gelesen["seiten"] += 1
        return {"data": jobs if gelesen["seiten"] == 1 else []}

    return antwort


def test_arbeitnow_uebersetzt_und_filtert(monkeypatch):
    jobs = [
        {"slug": "a", "title": "Data Engineer (m/w/d)", "company_name": "Beispiel GmbH",
         "location": "Hamburg", "description": "<p>Python und Kafka</p>",
         "created_at": 1756684800, "url": "https://x/a", "remote": False, "tags": ["IT"]},
        {"slug": "b", "title": "Vertriebsmitarbeiter", "company_name": "Andere GmbH",
         "location": "Hamburg", "description": "", "created_at": 1756684800,
         "url": "https://x/b", "remote": False},
        {"slug": "c", "title": "Data Engineer", "company_name": "Dritte GmbH",
         "location": "München", "description": "", "created_at": 1756684800,
         "url": "https://x/c", "remote": False},
    ]
    monkeypatch.setattr(basis, "hole_json", _seitenweise(jobs))
    monkeypatch.setattr(basis, "pause", lambda: None)

    treffer = list(arbeitnow.hole(config()))

    # b faellt am Titel, c am Ort.
    assert [t["referenznummer"] for t in treffer] == ["arbeitnow:a"]
    assert treffer[0]["stellenangebotsBeschreibung"] == "Python und Kafka"
    assert treffer[0]["firma"] == "Beispiel GmbH"


def test_arbeitnow_nimmt_remote_unabhaengig_vom_ort(monkeypatch):
    jobs = [{"slug": "r", "title": "Data Engineer", "company_name": "Fern GmbH",
             "location": "Berlin", "description": "", "created_at": 1756684800,
             "url": "https://x/r", "remote": "True"}]
    monkeypatch.setattr(basis, "hole_json", _seitenweise(jobs))
    monkeypatch.setattr(basis, "pause", lambda: None)

    treffer = list(arbeitnow.hole(config()))

    assert len(treffer) == 1
    assert treffer[0]["homeofficeprozent"] == 100


def test_arbeitnow_haelt_bei_zu_vielen_anfragen_an(monkeypatch):
    def bremst(url, kopfzeilen=None):
        raise basis.ZuVieleAnfragen("HTTP 429")

    monkeypatch.setattr(basis, "hole_json", bremst)
    monkeypatch.setattr(basis, "pause", lambda: None)

    # Kein Fehler nach aussen: was da ist, bleibt brauchbar.
    assert list(arbeitnow.hole(config())) == []


# --- Remotive ---------------------------------------------------------


def test_remotive_nimmt_nur_was_von_hier_aus_geht(monkeypatch):
    jobs = [
        {"id": 1, "title": "Data Engineer", "company_name": "A", "description": "x",
         "publication_date": "2026-08-17", "url": "https://a",
         "candidate_required_location": "Europe"},
        {"id": 2, "title": "Data Engineer", "company_name": "B", "description": "x",
         "publication_date": "2026-08-17", "url": "https://b",
         "candidate_required_location": "USA Only"},
    ]
    monkeypatch.setattr(basis, "hole_json", lambda url, kopfzeilen=None: {"jobs": jobs})

    treffer = list(remotive.hole(config()))

    assert [t["referenznummer"] for t in treffer] == ["remotive:1"]
    assert treffer[0]["homeofficeprozent"] == 100


# --- Remote OK --------------------------------------------------------


def test_remoteok_ueberspringt_den_hinweiskopf(monkeypatch):
    antwort = [
        {"legal": "Nutzungsbedingungen"},
        {"id": "7", "position": "Data Engineer", "company": "A", "description": "x",
         "date": "2026-08-17", "url": "https://a", "tags": ["data"]},
    ]
    monkeypatch.setattr(basis, "hole_json", lambda url, kopfzeilen=None: antwort)

    treffer = list(remoteok.hole(config()))

    assert [t["referenznummer"] for t in treffer] == ["remoteok:7"]


# --- Jobicy -----------------------------------------------------------


def test_jobicy_uebersetzt_die_eigenen_feldnamen(monkeypatch):
    antwort = {"jobs": [{
        "id": 9, "jobTitle": "Data Engineer", "companyName": "A",
        "jobDescription": "<p>Kafka</p>", "pubDate": "2026-08-17",
        "url": "https://a", "jobGeo": "Germany", "jobIndustry": ["Engineering"],
    }]}
    monkeypatch.setattr(basis, "hole_json", lambda url, kopfzeilen=None: antwort)

    treffer = list(jobicy.hole(config()))

    assert treffer[0]["referenznummer"] == "jobicy:9"
    assert treffer[0]["stellenangebotsBeschreibung"] == "Kafka"
    assert treffer[0]["firma"] == "A"


# --- Suchbegriffe -----------------------------------------------------


def test_katalogbegriff_nutzt_das_geprüfte_muster():
    """Java ist nicht JavaScript - die Teilzeichenkette wuerde das verwechseln."""
    assert basis.passt_zum_begriff("Java Entwickler (m/w/d)", ("Java",))
    assert basis.passt_zum_begriff("Java Software Engineer", ("Java",))
    assert not basis.passt_zum_begriff("JavaScript Developer", ("Java",))
    assert not basis.passt_zum_begriff("Senior TypeScript/JavaScript", ("Java",))


def test_zusammengeschriebene_titel_werden_gefunden():
    """Deutsche Stellentitel schreiben zusammen, deshalb Teilzeichenketten."""
    assert basis.passt_zum_begriff("Softwareentwickler Backend", ("Softwareentwickler",))
    assert basis.passt_zum_begriff("Anwendungsentwickler (m/w/d)", ("entwickler",))


def test_mehrere_begriffe_reichen_einzeln():
    begriffe = ("Data Engineer", "Developer", "Java")

    assert basis.passt_zum_begriff("Backend Developer", begriffe)
    assert basis.passt_zum_begriff("Data Platform Engineer", begriffe)
    assert not basis.passt_zum_begriff("Vertriebsmitarbeiter (m/w/d)", begriffe)


def test_leerer_titel_passt_nie():
    assert not basis.passt_zum_begriff("", ("Java",))


# --- Adzuna -----------------------------------------------------------


def test_adzuna_filtert_die_unscharfe_suche_nach(monkeypatch):
    """`what` sucht ueber den ganzen Text - der Titel entscheidet."""
    from poller.quellen import adzuna

    monkeypatch.setenv("ADZUNA_APP_ID", "kennung")
    monkeypatch.setenv("ADZUNA_APP_KEY", "schluessel")

    antwort = {
        "results": [
            {"id": 1, "title": "Data Engineer (m/w/d)", "company": {"display_name": "A"},
             "location": {"display_name": "Hamburg"}, "description": "x",
             "created": "2026-08-17", "redirect_url": "https://a"},
            {"id": 2, "title": "Bauingenieur Tragwerkplanung", "company": {"display_name": "B"},
             "location": {"display_name": "Hamburg"}, "description": "x",
             "created": "2026-08-17", "redirect_url": "https://b"},
        ]
    }
    monkeypatch.setattr(basis, "hole_json", lambda url, kopfzeilen=None: antwort)
    monkeypatch.setattr(basis, "pause", lambda: None)

    treffer = list(adzuna.hole(config()))

    assert [t["referenznummer"] for t in treffer] == ["adzuna:1"]


def test_adzuna_ohne_zugangsdaten_liefert_nichts(monkeypatch):
    from poller.quellen import adzuna

    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)

    assert list(adzuna.hole(config())) == []
