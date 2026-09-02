"""Konfiguration des Notifiers."""
from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    """Eine benoetigte Umgebungsvariable fehlt oder ist unbrauchbar."""


def _required(name: str) -> str:
    wert = os.environ.get(name, "").strip()
    if not wert:
        raise ConfigError(f"Umgebungsvariable {name} ist nicht gesetzt")
    return wert


@dataclass(frozen=True)
class KafkaConfig:
    bootstrap_servers: str
    topic_matched: str
    gruppe: str
    sasl_username: str
    sasl_password: str
    ca_cert_path: str

    @classmethod
    def from_env(cls) -> "KafkaConfig":
        return cls(
            bootstrap_servers=_required("KAFKA_BOOTSTRAP_SERVERS"),
            topic_matched=os.environ.get("KAFKA_TOPIC_MATCHED", "jobs.matched"),
            gruppe=os.environ.get("KAFKA_GROUP_ID", "notifier"),
            sasl_username=os.environ.get("KAFKA_SASL_USERNAME", "jobradar"),
            sasl_password=_passwort(),
            ca_cert_path=_required("KAFKA_CA_CERT_PATH"),
        )


def _passwort() -> str:
    direkt = os.environ.get("KAFKA_SASL_PASSWORD", "").strip()
    if direkt:
        return direkt

    parameter = os.environ.get("KAFKA_PASSWORD_SSM_PARAMETER", "").strip()
    if not parameter:
        raise ConfigError(
            "Weder KAFKA_SASL_PASSWORD noch KAFKA_PASSWORD_SSM_PARAMETER gesetzt"
        )

    import boto3

    antwort = boto3.client("ssm").get_parameter(Name=parameter, WithDecryption=True)
    return antwort["Parameter"]["Value"]


@dataclass(frozen=True)
class MailConfig:
    absender: str
    empfaenger: str
    # Gesammelt wird, bis eine der beiden Grenzen erreicht ist: entweder
    # genug Anzeigen beisammen oder lange genug nichts mehr eingetroffen.
    # Einzelmails pro Anzeige waeren nicht nur laestig, sondern wuerden
    # auch die Absenderreputation belasten.
    max_stapel: int
    wartezeit_sekunden: int

    @classmethod
    def from_env(cls) -> "MailConfig":
        return cls(
            absender=_required("SES_SENDER_ADDRESS"),
            empfaenger=_required("SES_RECIPIENT_ADDRESS"),
            max_stapel=int(os.environ.get("NOTIFIER_MAX_STAPEL", "25")),
            wartezeit_sekunden=int(os.environ.get("NOTIFIER_WARTEZEIT_SEKUNDEN", "60")),
        )
