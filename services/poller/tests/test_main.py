"""Test der Ablaufsteuerung."""
from poller import main
from poller.config import SearchConfig


def test_dieselbe_anzeige_aus_zwei_suchbegriffen_nur_einmal(monkeypatch):
    treffer = {
        "Data Engineer": [{"referenznummer": "a"}, {"referenznummer": "b"}],
        # b taucht unter beiden Begriffen auf.
        "Softwareentwickler": [{"referenznummer": "b"}, {"referenznummer": "c"}],
    }
    monkeypatch.setattr(
        main, "suche", lambda config, begriff, ortsgebunden=True: iter(treffer[begriff])
    )

    config = SearchConfig(
        base_url="https://example.invalid",
        api_key="test-key",
        suchbegriffe=("Data Engineer", "Softwareentwickler"),
        ort="Hamburg",
        umkreis_km=30,
        veroeffentlicht_seit_tagen=3,
        seitengroesse=50,
        remote_bundesweit=False,
        remote_min_prozent=100,
    )

    anzeigen = main.sammle_anzeigen(config)

    assert [job["referenznummer"] for job in anzeigen] == ["a", "b", "c"]


def test_anzeige_ohne_referenznummer_wird_uebersprungen(monkeypatch):
    monkeypatch.setattr(
        main,
        "suche",
        lambda config, begriff, ortsgebunden=True: iter(
            [{"stellenangebotsTitel": "ohne Nummer"}]
        ),
    )

    config = SearchConfig(
        base_url="https://example.invalid",
        api_key="test-key",
        suchbegriffe=("Data Engineer",),
        ort="Hamburg",
        umkreis_km=30,
        veroeffentlicht_seit_tagen=3,
        seitengroesse=50,
        remote_bundesweit=False,
        remote_min_prozent=100,
    )

    assert main.sammle_anzeigen(config) == []
