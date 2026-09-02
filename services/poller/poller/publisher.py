"""Veroeffentlicht Stellenanzeigen im Kafka-Topic jobs.raw."""
from __future__ import annotations

import json
import logging
from typing import Any, Iterable

from confluent_kafka import KafkaException, Producer

from .config import KafkaConfig
from .jobsuche import referenznummer

log = logging.getLogger(__name__)


def baue_producer(config: KafkaConfig) -> Producer:
    return Producer(
        {
            "bootstrap.servers": config.bootstrap_servers,
            # Der Broker ist oeffentlich erreichbar, die Anmeldung ist die
            # einzige Schranke (ADR 0002).
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "SCRAM-SHA-512",
            "sasl.username": config.sasl_username,
            "sasl.password": config.sasl_password,
            # Eigene CA als Vertrauensanker - es gibt keinen oeffentlich
            # anerkannten Aussteller fuer diesen Hostnamen.
            "ssl.ca.location": config.ca_cert_path,
            # Hostname-Pruefung bleibt aktiv; dafuer traegt das
            # Broker-Zertifikat ein Wildcard-SAN.
            "ssl.endpoint.identification.algorithm": "https",
            # Alle Kopien muessen bestaetigen, bevor eine Anzeige als
            # veroeffentlicht gilt. Bei einem Broker ist das derselbe
            # Rechner, kostet also nichts und bleibt bei Erweiterung
            # richtig.
            "acks": "all",
            "socket.timeout.ms": 15000,
        }
    )


def _bericht(fehler: Any, nachricht: Any) -> None:
    if fehler is not None:
        log.error("Zustellung fehlgeschlagen: %s", fehler)


def veroeffentliche(
    producer: Producer, topic: str, jobs: Iterable[dict[str, Any]]
) -> int:
    """Schreibt die Anzeigen ins Topic und wartet auf die Bestaetigung.

    Gibt zurueck, wie viele Anzeigen uebergeben wurden. Anzeigen ohne
    Referenznummer werden uebersprungen: ohne sie kann der nachgelagerte
    Dedup-Schritt sie nicht wiedererkennen.
    """
    anzahl = 0
    for job in jobs:
        schluessel = referenznummer(job)
        if schluessel is None:
            log.warning("Anzeige ohne Referenznummer uebersprungen: %s", job.get("stellenangebotsTitel"))
            continue

        producer.produce(
            topic=topic,
            # Gleicher Job, gleiche Partition - das haelt die Reihenfolge
            # pro Anzeige stabil und erlaubt spaeter Log Compaction.
            key=schluessel.encode("utf-8"),
            value=json.dumps(job, ensure_ascii=False).encode("utf-8"),
            on_delivery=_bericht,
        )
        anzahl += 1

    # flush blockiert, bis alle Nachrichten bestaetigt sind. In einer
    # Lambda ist das zwingend: ohne flush endet der Aufruf womoeglich,
    # bevor etwas den Broker erreicht hat.
    verblieben = producer.flush(timeout=30)
    if verblieben:
        raise KafkaException(f"{verblieben} Nachrichten konnten nicht zugestellt werden")

    return anzahl
