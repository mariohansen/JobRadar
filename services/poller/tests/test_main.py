"""Test der Ablaufsteuerung."""
from poller import main
from poller.config import SearchConfig
from poller.quellen import arbeitsagentur, basis


def config(**abweichend):
    werte = dict(
        base_url="https://example.invalid",
        api_key="test-key",
        suchbegriffe=("Data Engineer",),
        ort="Hamburg",
        umkreis_km=30,
        veroeffentlicht_seit_tagen=3,
        seitengroesse=50,
        remote_bundesweit=False,
        remote_min_prozent=100,
        quellen=("arbeitsagentur",),
    )
    werte.update(abweichend)
    return SearchConfig(**werte)


def test_dieselbe_anzeige_aus_zwei_suchbegriffen_nur_einmal(monkeypatch):
    treffer = {
        "Data Engineer": [{"referenznummer": "a"}, {"referenznummer": "b"}],
        # b taucht unter beiden Begriffen auf.
        "Softwareentwickler": [{"referenznummer": "b"}, {"referenznummer": "c"}],
    }
    monkeypatch.setattr(
        arbeitsagentur,
        "suche",
        lambda cfg, begriff, ortsgebunden=True: iter(treffer[begriff]),
    )

    anzeigen = main.sammle_anzeigen(
        config(suchbegriffe=("Data Engineer", "Softwareentwickler"))
    )

    assert [job["referenznummer"] for job in anzeigen] == ["a", "b", "c"]


def test_anzeige_ohne_referenznummer_wird_uebersprungen(monkeypatch):
    monkeypatch.setattr(
        arbeitsagentur,
        "suche",
        lambda cfg, begriff, ortsgebunden=True: iter(
            [{"stellenangebotsTitel": "ohne Nummer"}]
        ),
    )

    assert main.sammle_anzeigen(config()) == []


def test_herkunft_wird_vermerkt(monkeypatch):
    monkeypatch.setattr(
        arbeitsagentur,
        "suche",
        lambda cfg, begriff, ortsgebunden=True: iter([{"referenznummer": "a"}]),
    )

    anzeigen = main.sammle_anzeigen(config())

    assert anzeigen[0]["quelle"] == "arbeitsagentur"


# --- Quellenuebergreifend ---------------------------------------------


def _stelle(referenz, firma="Beispiel GmbH", titel="Data Engineer (m/w/d)"):
    return {
        "referenznummer": referenz,
        "firma": firma,
        "stellenangebotsTitel": titel,
        "stellenlokationen": [{"adresse": {"ort": "Hamburg"}}],
    }


def test_dieselbe_stelle_aus_zwei_quellen_nur_einmal(monkeypatch):
    """Verschiedene Kennungen, gleicher Inhalt - der Fingerabdruck faengt das."""
    monkeypatch.setattr(
        arbeitsagentur,
        "suche",
        lambda cfg, begriff, ortsgebunden=True: iter([_stelle("10001-1-S")]),
    )
    # Dieselbe Stelle, aber vom anderen Portal und leicht anders geschrieben.
    monkeypatch.setattr(
        basis,
        "hole_json",
        lambda url, kopfzeilen=None: {
            "data": [
                {
                    "slug": "data-engineer-hamburg",
                    "title": "Data Engineer (w/m/d)",
                    "company_name": "Beispiel GmbH & Co. KG",
                    "location": "Hamburg",
                    "description": "",
                    "created_at": None,
                    "url": "https://arbeitnow.example/a",
                    "remote": False,
                }
            ]
        },
    )
    monkeypatch.setattr(basis, "pause", lambda: None)

    anzeigen = main.sammle_anzeigen(
        config(quellen=("arbeitsagentur", "arbeitnow"))
    )

    assert [job["referenznummer"] for job in anzeigen] == ["10001-1-S"]


def test_verschiedene_stellen_bleiben_beide(monkeypatch):
    monkeypatch.setattr(
        arbeitsagentur,
        "suche",
        lambda cfg, begriff, ortsgebunden=True: iter(
            [_stelle("10001-1-S"), _stelle("10001-2-S", firma="Andere GmbH")]
        ),
    )

    anzeigen = main.sammle_anzeigen(config())

    assert len(anzeigen) == 2


def test_eine_ausgefallene_quelle_kippt_den_lauf_nicht(monkeypatch):
    def kaputt(cfg):
        raise basis.QuellenFehler("HTTP 500")

    monkeypatch.setattr(
        arbeitsagentur,
        "suche",
        lambda cfg, begriff, ortsgebunden=True: iter([_stelle("10001-1-S")]),
    )
    monkeypatch.setattr("poller.quellen.arbeitnow.hole", kaputt)

    anzeigen = main.sammle_anzeigen(config(quellen=("arbeitnow", "arbeitsagentur")))

    assert [job["referenznummer"] for job in anzeigen] == ["10001-1-S"]


def test_quelle_ohne_zugangsdaten_wird_uebersprungen(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    monkeypatch.setattr(
        arbeitsagentur,
        "suche",
        lambda cfg, begriff, ortsgebunden=True: iter([_stelle("10001-1-S")]),
    )

    anzeigen = main.sammle_anzeigen(config(quellen=("adzuna", "arbeitsagentur")))

    assert [job["referenznummer"] for job in anzeigen] == ["10001-1-S"]
