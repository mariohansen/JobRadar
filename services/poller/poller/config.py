"""Konfiguration des Pollers.

Alle Werte kommen aus Umgebungsvariablen - nichts ist hartkodiert. Das
Kafka-Passwort bildet die Ausnahme von der einfachen Regel: lokal darf es
direkt in der Umgebung stehen, in der Lambda wird stattdessen der Name
eines SSM-Parameters gesetzt und der Wert zur Laufzeit geholt.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    """Eine benoetigte Umgebungsvariable fehlt oder ist unbrauchbar."""


# Die Jobsuche-API akzeptiert bei veroeffentlichtseit nur diese Werte -
# es sind die Zeitraum-Schaltflaechen ihrer eigenen Oberflaeche. Jeder
# andere Wert wird kommentarlos verworfen, die Antwort enthaelt dann
# saemtliche Treffer statt der erwarteten Auswahl. Weil die API das nicht
# als Fehler meldet, pruefen wir es hier.
ERLAUBTES_ZEITFENSTER = (0, 1, 7, 14, 28)


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"Umgebungsvariable {name} ist nicht gesetzt")
    return value


def _bool(name: str, default: bool) -> bool:
    roh = os.environ.get(name, "").strip().lower()
    if not roh:
        return default
    if roh in ("true", "1", "ja", "yes"):
        return True
    if roh in ("false", "0", "nein", "no"):
        return False
    raise ConfigError(f"{name} muss wahr oder falsch sein, ist aber {roh!r}")


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} muss eine ganze Zahl sein, ist aber {raw!r}") from exc


def _zeitfenster(name: str, default: int) -> int:
    wert = _int(name, default)
    if wert not in ERLAUBTES_ZEITFENSTER:
        erlaubt = ", ".join(str(z) for z in ERLAUBTES_ZEITFENSTER)
        raise ConfigError(
            f"{name}={wert} wird von der API stillschweigend ignoriert. "
            f"Erlaubt sind nur: {erlaubt}"
        )
    return wert


@dataclass(frozen=True)
class SearchConfig:
    """Suchprofil fuer die Jobsuche-API."""

    base_url: str
    api_key: str
    suchbegriffe: tuple[str, ...]
    ort: str
    umkreis_km: int
    veroeffentlicht_seit_tagen: int
    seitengroesse: int
    # Zweiter Durchgang ohne Ortsbindung, der nur Anzeigen mitnimmt, die
    # vollstaendig aus dem Homeoffice erledigt werden koennen. Ohne diese
    # Einschraenkung waere der Suchraum ganz Deutschland.
    remote_bundesweit: bool
    remote_min_prozent: int

    @classmethod
    def from_env(cls) -> "SearchConfig":
        begriffe = tuple(
            teil.strip()
            for teil in os.environ.get("JOBSUCHE_WAS", "Data Engineer").split(",")
            if teil.strip()
        )
        if not begriffe:
            raise ConfigError("JOBSUCHE_WAS enthaelt keinen Suchbegriff")

        return cls(
            base_url=os.environ.get(
                "JOBSUCHE_BASE_URL",
                "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service",
            ).rstrip("/"),
            # Kein Geheimnis: die clientId ist oeffentlich bekannt. Steht
            # trotzdem in der Konfiguration, damit sie bei einer Aenderung
            # nicht im Code gesucht werden muss.
            api_key=os.environ.get("JOBSUCHE_API_KEY", "jobboerse-jobsuche"),
            suchbegriffe=begriffe,
            ort=os.environ.get("JOBSUCHE_WO", "Hamburg"),
            umkreis_km=_int("JOBSUCHE_UMKREIS_KM", 30),
            # Sieben Tage als Puffer: faellt ein Lauf aus, gehen die
            # Anzeigen der Vortage nicht verloren. Wiederholungen sind
            # unkritisch, die filtert der Dedup-Schritt heraus.
            veroeffentlicht_seit_tagen=_zeitfenster("JOBSUCHE_VEROEFFENTLICHT_SEIT_TAGEN", 7),
            seitengroesse=_int("JOBSUCHE_SEITENGROESSE", 50),
            remote_bundesweit=_bool("JOBSUCHE_REMOTE_BUNDESWEIT", True),
            # 100 bedeutet: die Stelle ist vollstaendig aus dem Homeoffice
            # zu erledigen. Niedrigere Werte lassen auch Stellen zu, die
            # nur teilweise remote sind - dann ist die Entfernung zum
            # Arbeitsort wieder ein Thema.
            remote_min_prozent=_int("JOBSUCHE_REMOTE_MIN_PROZENT", 100),
        )


@dataclass(frozen=True)
class KafkaConfig:
    """Verbindungsdaten des Brokers."""

    bootstrap_servers: str
    topic: str
    sasl_username: str
    sasl_password: str
    ca_cert_path: str

    @classmethod
    def from_env(cls) -> "KafkaConfig":
        return cls(
            # Muss der DNS-Name sein, nicht die IP: gegen eine IP schlaegt
            # die Pruefung des Wildcard-Zertifikats fehl.
            bootstrap_servers=_required("KAFKA_BOOTSTRAP_SERVERS"),
            topic=os.environ.get("KAFKA_TOPIC_RAW", "jobs.raw"),
            sasl_username=os.environ.get("KAFKA_SASL_USERNAME", "jobradar"),
            sasl_password=_resolve_password(),
            ca_cert_path=_resolve_ca_cert(),
        )


def _resolve_ca_cert() -> str:
    """Pfad zum CA-Zertifikat.

    Lokal zeigt KAFKA_CA_CERT_PATH auf eine Datei. In der Lambda gibt es
    keine, dort steht der Name eines SSM-Parameters - dessen Inhalt wird
    nach /tmp geschrieben, dem einzigen beschreibbaren Verzeichnis einer
    Lambda.
    """
    pfad = os.environ.get("KAFKA_CA_CERT_PATH", "").strip()
    if pfad:
        return pfad

    parameter = os.environ.get("KAFKA_CA_CERT_SSM_PARAMETER", "").strip()
    if not parameter:
        raise ConfigError(
            "Weder KAFKA_CA_CERT_PATH noch KAFKA_CA_CERT_SSM_PARAMETER gesetzt"
        )

    ziel = "/tmp/kafka-ca.crt"
    # Zwischen zwei Aufrufen derselben Lambda-Instanz bleibt /tmp
    # erhalten - dann sparen wir uns den zweiten SSM-Aufruf.
    if not os.path.exists(ziel):
        with open(ziel, "w", encoding="utf-8") as datei:
            datei.write(_ssm_wert(parameter))
    return ziel


def _ssm_wert(name: str) -> str:
    import boto3  # nur noetig, wenn wirklich ueber SSM gelesen wird

    antwort = boto3.client("ssm").get_parameter(Name=name, WithDecryption=True)
    return antwort["Parameter"]["Value"]


def _resolve_password() -> str:
    """Passwort aus der Umgebung oder, falls dort nicht gesetzt, aus SSM.

    Der direkte Weg ist fuer lokale Laeufe gedacht, der SSM-Weg fuer die
    Lambda - dort liegt kein Geheimnis in der Funktionskonfiguration,
    sondern nur der Name des Parameters.
    """
    direkt = os.environ.get("KAFKA_SASL_PASSWORD", "").strip()
    if direkt:
        return direkt

    parameter = os.environ.get("KAFKA_PASSWORD_SSM_PARAMETER", "").strip()
    if not parameter:
        raise ConfigError(
            "Weder KAFKA_SASL_PASSWORD noch KAFKA_PASSWORD_SSM_PARAMETER gesetzt"
        )

    return _ssm_wert(parameter)
