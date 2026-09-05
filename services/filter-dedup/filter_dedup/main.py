"""Filter- und Dedup-Consumer.

Liest jobs.raw, archiviert jede Anzeige, verwirft bereits bekannte,
anderswo schon gemeldete und unpassende und schreibt den Rest nach
jobs.matched.
"""
from __future__ import annotations

import json
import logging
import signal
import sys
from types import FrameType
from typing import Any

from confluent_kafka import Consumer, KafkaError, Producer

from gemeinsam import fingerabdruck
from gemeinsam.archiv import Archiv

from .anreicherung import Anreicherung, sicher_ergaenzen
from .config import ConfigError, FilterConfig, KafkaConfig
from .dedup import Dedup
from .matching import passt

log = logging.getLogger(__name__)

_laeuft = True


def _beenden(signum: int, rahmen: FrameType | None) -> None:
    """Auf SIGTERM sauber aussteigen.

    systemd schickt beim Stoppen SIGTERM. Ohne diese Behandlung wuerde
    der Prozess mitten in der Verarbeitung abbrechen - moeglicherweise
    nach dem Schreiben, aber vor dem Bestaetigen des Offsets.
    """
    global _laeuft
    log.info("Signal %s empfangen, beende nach der laufenden Nachricht", signum)
    _laeuft = False


def sicherheitsoptionen(config: KafkaConfig) -> dict[str, Any]:
    return {
        "bootstrap.servers": config.bootstrap_servers,
        "security.protocol": "SASL_SSL",
        "sasl.mechanisms": "SCRAM-SHA-512",
        "sasl.username": config.sasl_username,
        "sasl.password": config.sasl_password,
        "ssl.ca.location": config.ca_cert_path,
        "ssl.endpoint.identification.algorithm": "https",
    }


def baue_consumer(config: KafkaConfig) -> Consumer:
    return Consumer(
        {
            **sicherheitsoptionen(config),
            "group.id": config.gruppe,
            # Beim ersten Start alles von vorne lesen. Sonst gingen die
            # Anzeigen verloren, die zwischen einem Poller-Lauf und dem
            # Start des Consumers eingetroffen sind.
            "auto.offset.reset": "earliest",
            # Offsets werden erst nach erfolgreicher Verarbeitung
            # bestaetigt. Bei einem Absturz wird die Nachricht erneut
            # zugestellt - unproblematisch, weil der Dedup-Schritt eine
            # Wiederholung folgenlos macht.
            "enable.auto.commit": False,
        }
    )


def verarbeite(
    job: dict[str, Any],
    referenznummer: str,
    archiv: Archiv,
    dedup: Dedup,
    filter_config: FilterConfig,
    producer: Producer,
    topic_matched: str,
    anreicherung: Anreicherung | None = None,
) -> str:
    """Verarbeitet eine Anzeige und meldet zurueck, was mit ihr geschah."""
    # Archiviert wird vor jeder Filterung: das Archiv soll den
    # vollstaendigen Rohbestand enthalten, auch die aussortierten. Und
    # unveraendert - die Anreicherung kommt erst danach dazu.
    archiv.ablegen(referenznummer, job)

    if not dedup.ist_neu(referenznummer, job.get("stellenangebotsTitel", "")):
        return "bekannt"

    # Die Kennung ist nur innerhalb einer Quelle eindeutig. Dieselbe
    # Stelle steht oft auf mehreren Portalen - der inhaltliche
    # Fingerabdruck aus Arbeitgeber, Titel und Ort faengt das ab.
    schluessel = fingerabdruck.schluessel(job)
    if schluessel is not None and not dedup.ist_inhaltlich_neu(schluessel, referenznummer):
        return "doppelt"

    if not passt(
        job,
        filter_config.ausschluss,
        filter_config.pflicht,
        filter_config.arbeitgeber,
    ):
        return "aussortiert"

    # Erst hier, nach Dedup und Filter: nur was wirklich neu ist und
    # durchkommt, ist einen Abruf des Anzeigentextes wert.
    sicher_ergaenzen(anreicherung, job, referenznummer)

    producer.produce(
        topic=topic_matched,
        key=referenznummer.encode("utf-8"),
        value=json.dumps(job, ensure_ascii=False).encode("utf-8"),
    )
    return "weitergereicht"


def _profil(filter_config: FilterConfig):
    """Faehigkeitsprofil, falls eines ausgerollt wurde.

    Fehlt es oder ist es unlesbar, laeuft die Pipeline ohne Bewertung
    weiter - das ist der Zustand, in dem sie bisher lief.
    """
    if not filter_config.profil_pfad:
        log.info("Kein Profil gesetzt, Anzeigen werden nicht bewertet")
        return None

    from pathlib import Path

    from gemeinsam import profil as pr

    try:
        geladen = pr.lade(Path(filter_config.profil_pfad))
    except pr.ProfilFehler as exc:
        log.warning("Profil nicht geladen, keine Bewertung: %s", exc)
        return None

    log.info("Profil geladen: %s Faehigkeiten", len(geladen.alle))
    return geladen


def run() -> dict[str, int]:
    kafka_config = KafkaConfig.from_env()
    filter_config = FilterConfig.from_env()

    archiv = Archiv(filter_config.bucket)
    dedup = Dedup(filter_config.tabelle, filter_config.aufbewahrung_tage)
    anreicherung = Anreicherung(
        archiv, _profil(filter_config), filter_config.mit_details
    )
    producer = Producer({**sicherheitsoptionen(kafka_config), "acks": "all"})

    consumer = baue_consumer(kafka_config)
    consumer.subscribe([kafka_config.topic_raw])
    log.info("Lese %s als Gruppe %s", kafka_config.topic_raw, kafka_config.gruppe)

    zaehler = {"bekannt": 0, "doppelt": 0, "aussortiert": 0, "weitergereicht": 0}

    try:
        while _laeuft:
            nachricht = consumer.poll(timeout=1.0)
            if nachricht is None:
                continue
            if nachricht.error():
                if nachricht.error().code() == KafkaError._PARTITION_EOF:
                    continue
                log.error("Kafka-Fehler: %s", nachricht.error())
                continue

            schluessel = nachricht.key()
            if schluessel is None:
                log.warning("Nachricht ohne Schluessel uebersprungen")
                consumer.commit(nachricht)
                continue

            referenznummer = schluessel.decode("utf-8")
            job = json.loads(nachricht.value())
            ergebnis = verarbeite(
                job,
                referenznummer,
                archiv,
                dedup,
                filter_config,
                producer,
                kafka_config.topic_matched,
                anreicherung,
            )
            zaehler[ergebnis] += 1

            # Erst zustellen lassen, dann den Offset bestaetigen. Die
            # umgekehrte Reihenfolge koennte eine Anzeige verlieren.
            producer.flush(timeout=15)
            consumer.commit(nachricht)

            if ergebnis == "weitergereicht":
                log.info("Neu: %s (%s)", job.get("stellenangebotsTitel"), referenznummer)
    finally:
        consumer.close()
        producer.flush(timeout=15)
        log.info(
            "Beendet. %s weitergereicht, %s bekannt, %s doppelt (andere Quelle), "
            "%s aussortiert",
            zaehler["weitergereicht"],
            zaehler["bekannt"],
            zaehler["doppelt"],
            zaehler["aussortiert"],
        )

    return zaehler


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )
    signal.signal(signal.SIGTERM, _beenden)
    signal.signal(signal.SIGINT, _beenden)

    try:
        run()
    except ConfigError as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
