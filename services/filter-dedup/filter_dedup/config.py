"""Konfiguration des Filter- und Dedup-Consumers."""
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


def _liste(name: str, vorgabe: str = "") -> tuple[str, ...]:
    roh = os.environ.get(name, vorgabe)
    return tuple(teil.strip().lower() for teil in roh.split(",") if teil.strip())


@dataclass(frozen=True)
class KafkaConfig:
    bootstrap_servers: str
    topic_raw: str
    topic_matched: str
    gruppe: str
    sasl_username: str
    sasl_password: str
    ca_cert_path: str

    @classmethod
    def from_env(cls) -> "KafkaConfig":
        return cls(
            bootstrap_servers=_required("KAFKA_BOOTSTRAP_SERVERS"),
            topic_raw=os.environ.get("KAFKA_TOPIC_RAW", "jobs.raw"),
            topic_matched=os.environ.get("KAFKA_TOPIC_MATCHED", "jobs.matched"),
            # Die Consumer-Gruppe bestimmt, welche Offsets Kafka fuer uns
            # merkt. Ein anderer Name laesst denselben Datenstrom von
            # vorne lesen, ohne den bisherigen Fortschritt zu verlieren.
            gruppe=os.environ.get("KAFKA_GROUP_ID", "filter-dedup"),
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
class FilterConfig:
    tabelle: str
    bucket: str
    ausschluss: tuple[str, ...]
    pflicht: tuple[str, ...]
    aufbewahrung_tage: int

    @classmethod
    def from_env(cls) -> "FilterConfig":
        return cls(
            tabelle=_required("DYNAMODB_TABLE_SEEN_JOBS"),
            bucket=_required("S3_BUCKET_RAW_ARCHIVE"),
            # Anzeigen, die zwar zum Suchbegriff passen, aber nicht zur
            # Lebenslage - der haeufigste Grund fuer unbrauchbare Treffer.
            #
            # Drei Gruppen:
            #
            # Erfahrungsstufe: "senior" und "sr". Verglichen wird auf den
            # Wortanfang, deshalb deckt "sr" auch "Sr." ab, ohne in
            # "Israel" anzuschlagen.
            #
            # Fuehrungsrollen: "lead" erfasst auch "Leader", braucht aber
            # "teamlead" als eigenen Eintrag, weil dort kein Wortanfang
            # steht. Dasselbe gilt fuer "leiter" und "teamleiter".
            #
            # Bewusst nicht dabei: "manager". Der Begriff steht auch in
            # Titeln wie "Junior Customer Success Manager" und wuerde
            # damit Einstiegsstellen aussortieren.
            ausschluss=_liste(
                "MATCH_AUSSCHLUSS",
                "praktikum,werkstudent,ausbildung,minijob,aushilfe,"
                "schulpraktikum,senior,sr,"
                "lead,teamlead,leiter,teamleiter,principal,staff,head of",
            ),
            # Leer bedeutet: keine Einschraenkung. Sonst muss mindestens
            # einer dieser Begriffe vorkommen.
            pflicht=_liste("MATCH_PFLICHT"),
            aufbewahrung_tage=int(os.environ.get("DEDUP_AUFBEWAHRUNG_TAGE", "180")),
        )
