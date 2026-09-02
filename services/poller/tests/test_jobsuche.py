"""Tests des API-Clients. Laufen ohne Netzzugriff."""
import urllib.parse

import pytest

from poller import jobsuche
from poller.config import SearchConfig


def baue_config(**abweichungen):
    werte = dict(
        base_url="https://example.invalid/jobsuche-service",
        api_key="test-key",
        suchbegriffe=("Data Engineer",),
        ort="Hamburg",
        umkreis_km=30,
        veroeffentlicht_seit_tagen=3,
        seitengroesse=2,
        remote_bundesweit=True,
        remote_min_prozent=100,
    )
    werte.update(abweichungen)
    return SearchConfig(**werte)


def test_url_enthaelt_alle_suchparameter():
    url = jobsuche.baue_url(baue_config(), "Data Engineer", seite=1)

    assert url.startswith("https://example.invalid/jobsuche-service/pc/v6/jobs?")
    assert "was=Data+Engineer" in url
    assert "wo=Hamburg" in url
    assert "umkreis=30" in url
    assert "veroeffentlichtseit=3" in url
    assert "page=1" in url


def test_suche_laeuft_ueber_mehrere_seiten(monkeypatch):
    seiten = {
        1: {"ergebnisliste": [{"referenznummer": "a"}, {"referenznummer": "b"}]},
        2: {"ergebnisliste": [{"referenznummer": "c"}]},
    }
    abgerufen = []

    def fake_hole(url, api_key):
        # Ueber die Parameter parsen statt die Zeichenkette zu zerlegen -
        # sonst haengt der Test an der Reihenfolge in der URL.
        parameter = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        seite = int(parameter["page"][0])
        abgerufen.append(seite)
        return seiten.get(seite, {"ergebnisliste": []})

    monkeypatch.setattr(jobsuche, "_hole", fake_hole)

    treffer = list(jobsuche.suche(baue_config(), "Data Engineer"))

    assert [job["referenznummer"] for job in treffer] == ["a", "b", "c"]
    # Seite 2 war nicht voll, also darf keine dritte Anfrage folgen.
    assert abgerufen == [1, 2]


def test_suche_endet_bei_leerer_seite(monkeypatch):
    monkeypatch.setattr(jobsuche, "_hole", lambda url, api_key: {"ergebnisliste": []})

    assert list(jobsuche.suche(baue_config(), "Data Engineer")) == []


def test_referenznummer_fehlt():
    assert jobsuche.referenznummer({"referenznummer": "10001-1003552327-S"}) == "10001-1003552327-S"
    assert jobsuche.referenznummer({}) is None
    assert jobsuche.referenznummer({"referenznummer": ""}) is None


def test_bundesweite_suche_laesst_ort_und_umkreis_weg():
    url = jobsuche.baue_url(baue_config(), "Data Engineer", 1, ortsgebunden=False)

    assert "wo=" not in url
    assert "umkreis=" not in url
    assert "was=Data+Engineer" in url


def test_ortsgebundene_suche_setzt_ort_und_umkreis():
    url = jobsuche.baue_url(baue_config(), "Data Engineer", 1, ortsgebunden=True)

    assert "wo=Hamburg" in url
    assert "umkreis=30" in url


def test_vollstaendig_remote_wird_erkannt():
    assert jobsuche.ist_vollstaendig_remote({"homeofficeprozent": 100}, 100) is True


def test_teilweises_homeoffice_reicht_nicht():
    assert jobsuche.ist_vollstaendig_remote({"homeofficeprozent": 60}, 100) is False


def test_nach_vereinbarung_gilt_nicht_als_remote():
    """Nur der Prozentwert ist belastbar - NACH_VEREINBARUNG heisst nur,
    dass darueber gesprochen werden kann."""
    anzeige = {"homeofficemoeglich": True, "homeofficetyp": "NACH_VEREINBARUNG"}

    assert jobsuche.ist_vollstaendig_remote(anzeige, 100) is False


def test_anzeige_ohne_homeoffice_angabe():
    assert jobsuche.ist_vollstaendig_remote({}, 100) is False


def test_niedrigere_schwelle_laesst_teilzeit_remote_zu():
    assert jobsuche.ist_vollstaendig_remote({"homeofficeprozent": 80}, 80) is True
