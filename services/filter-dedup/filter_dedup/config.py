"""Konfiguration des Filter- und Dedup-Consumers."""
from __future__ import annotations

import os
from dataclasses import dataclass

from gemeinsam.ausschluss import ARBEITGEBER as STANDARD_ARBEITGEBER
from gemeinsam.ausschluss import STANDARD as STANDARD_AUSSCHLUSS


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
    profil_pfad: str
    mit_details: bool
    ausschluss: tuple[str, ...]
    arbeitgeber: tuple[str, ...]
    pflicht: tuple[str, ...]
    aufbewahrung_tage: int

    @classmethod
    def from_env(cls) -> "FilterConfig":
        return cls(
            tabelle=_required("DYNAMODB_TABLE_SEEN_JOBS"),
            bucket=_required("S3_BUCKET_RAW_ARCHIVE"),
            # Anzeigen, die zwar zum Suchbegriff passen, aber nicht zur
            # Lebenslage - der haeufigste Grund fuer unbrauchbare Treffer.
            # Die Liste und die Begruendung stehen in
            # gemeinsam.ausschluss, damit der tracker dieselbe anwendet.
            # Leer oder nicht gesetzt bedeutet: die Vorgabe von dort.
            ausschluss=_liste("MATCH_AUSSCHLUSS") or STANDARD_AUSSCHLUSS,
            # Arbeitgeber statt Fachrichtung - geprueft wird der
            # Firmenname, nicht der Titel.
            arbeitgeber=_liste("MATCH_ARBEITGEBER_AUSSCHLUSS") or STANDARD_ARBEITGEBER,
            # Leer bedeutet: keine Einschraenkung. Sonst muss mindestens
            # einer dieser Begriffe vorkommen.
            pflicht=_liste("MATCH_PFLICHT"),
            # Ohne Profil laeuft alles wie bisher, nur ohne Bewertung.
            # Die Datei legt das Ausrollskript ab; ins Repo gehoert sie
            # nicht.
            profil_pfad=os.environ.get("JOBRADAR_PROFIL", "").strip(),
            # Der Anzeigentext kostet je neuer Anzeige einen Abruf. Wer
            # das nicht will, verliert nur die Bewertung.
            mit_details=os.environ.get("FILTER_DETAILS", "true").strip().lower()
            not in ("false", "0", "nein", "no"),
            aufbewahrung_tage=int(os.environ.get("DEDUP_AUFBEWAHRUNG_TAGE", "180")),
        )
