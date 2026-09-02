"""Tests der Konfiguration."""
import pytest

from poller.config import ConfigError, KafkaConfig, SearchConfig


def test_suchbegriffe_werden_getrennt(monkeypatch):
    monkeypatch.setenv("JOBSUCHE_WAS", "Data Engineer, Softwareentwickler ")

    config = SearchConfig.from_env()

    assert config.suchbegriffe == ("Data Engineer", "Softwareentwickler")


def test_vorgabewerte_greifen(monkeypatch):
    monkeypatch.delenv("JOBSUCHE_WAS", raising=False)
    monkeypatch.delenv("JOBSUCHE_UMKREIS_KM", raising=False)

    config = SearchConfig.from_env()

    assert config.ort == "Hamburg"
    assert config.umkreis_km == 30
    assert config.base_url.endswith("/jobsuche-service")


def test_zahl_muss_ganzzahlig_sein(monkeypatch):
    monkeypatch.setenv("JOBSUCHE_UMKREIS_KM", "dreissig")

    with pytest.raises(ConfigError, match="ganze Zahl"):
        SearchConfig.from_env()


def test_kafka_ohne_broker_adresse(monkeypatch):
    monkeypatch.delenv("KAFKA_BOOTSTRAP_SERVERS", raising=False)

    with pytest.raises(ConfigError, match="KAFKA_BOOTSTRAP_SERVERS"):
        KafkaConfig.from_env()


def test_kafka_ohne_passwortquelle(monkeypatch):
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker.invalid:9094")
    monkeypatch.setenv("KAFKA_CA_CERT_PATH", "ca.crt")
    monkeypatch.delenv("KAFKA_SASL_PASSWORD", raising=False)
    monkeypatch.delenv("KAFKA_PASSWORD_SSM_PARAMETER", raising=False)

    with pytest.raises(ConfigError, match="KAFKA_PASSWORD_SSM_PARAMETER"):
        KafkaConfig.from_env()


def test_ungueltiges_zeitfenster_wird_abgelehnt(monkeypatch):
    """Die API verwirft unbekannte Werte kommentarlos und liefert dann
    alle Treffer. Der Fehler muss deshalb hier auffallen."""
    monkeypatch.setenv("JOBSUCHE_VEROEFFENTLICHT_SEIT_TAGEN", "3")

    with pytest.raises(ConfigError, match="stillschweigend ignoriert"):
        SearchConfig.from_env()


def test_erlaubtes_zeitfenster_geht_durch(monkeypatch):
    monkeypatch.setenv("JOBSUCHE_VEROEFFENTLICHT_SEIT_TAGEN", "14")

    assert SearchConfig.from_env().veroeffentlicht_seit_tagen == 14


def test_ca_zertifikat_ohne_quelle(monkeypatch):
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker.invalid:9094")
    monkeypatch.setenv("KAFKA_SASL_PASSWORD", "geheim")
    monkeypatch.delenv("KAFKA_CA_CERT_PATH", raising=False)
    monkeypatch.delenv("KAFKA_CA_CERT_SSM_PARAMETER", raising=False)

    with pytest.raises(ConfigError, match="KAFKA_CA_CERT_SSM_PARAMETER"):
        KafkaConfig.from_env()
