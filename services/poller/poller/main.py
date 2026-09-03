"""Einstiegspunkt des Pollers.

Fragt die Jobsuche-API ab und schreibt die Treffer nach jobs.raw. Ob eine
Anzeige schon einmal gesehen wurde, entscheidet nicht dieser Dienst,
sondern der nachgelagerte filter-dedup-Consumer gegen DynamoDB.
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any

from gemeinsam import fingerabdruck

from . import quellen
from .config import ConfigError, KafkaConfig, SearchConfig
from .jobsuche import JobsucheError, referenznummer
from .publisher import baue_producer, veroeffentliche

log = logging.getLogger(__name__)


def sammle_anzeigen(config: SearchConfig) -> list[dict[str, Any]]:
    """Treffer aller eingestellten Quellen, ohne Doppelte.

    Doppelte entstehen auf drei Wegen: dieselbe Anzeige unter zwei
    Suchbegriffen, eine Hamburger Stelle, die zugleich vollstaendig
    remote ist, und - seit es mehrere Quellen gibt - dieselbe Stelle auf
    zwei Portalen. Die ersten beiden faengt die Referenznummer ab, den
    dritten der inhaltliche Fingerabdruck aus Arbeitgeber, Titel und Ort.

    Das ersetzt keine Deduplizierung gegenueber frueheren Laeufen; dafuer
    ist der filter-dedup-Consumer zustaendig, der denselben Fingerabdruck
    gegen DynamoDB prueft.

    Faellt eine Quelle aus, laufen die uebrigen weiter. Eine Boerse ohne
    Vertrag darf den ganzen Lauf nicht verhindern.
    """
    gesehen: set[str] = set()
    inhalte: set[str] = set()
    anzeigen: list[dict[str, Any]] = []

    def aufnehmen(job: dict[str, Any]) -> bool:
        nummer = referenznummer(job)
        if nummer is None or nummer in gesehen:
            return False

        # Ohne Arbeitgeber oder Titel gibt es keinen belastbaren
        # Fingerabdruck. Dann zaehlt nur die Referenznummer.
        abdruck = fingerabdruck.berechne(job)
        if abdruck is not None and abdruck in inhalte:
            return False

        gesehen.add(nummer)
        if abdruck is not None:
            inhalte.add(abdruck)
        anzeigen.append(job)
        return True

    for name in config.quellen:
        if not quellen.ist_verfuegbar(name):
            log.info("Quelle %s uebersprungen: keine Zugangsdaten", name)
            continue

        vorher = len(anzeigen)
        try:
            for job in quellen.hole(name, config):
                aufnehmen(job)
        except Exception as exc:  # eine Boerse darf den Lauf nicht kippen
            log.warning("Quelle %s uebersprungen: %s", name, exc)
            continue

        log.info("%s: %s neue Anzeigen", name, len(anzeigen) - vorher)

    return anzeigen


def run() -> dict[str, int]:
    such_config = SearchConfig.from_env()
    kafka_config = KafkaConfig.from_env()

    anzeigen = sammle_anzeigen(such_config)
    if not anzeigen:
        log.info("Keine Anzeigen im Zeitfenster von %s Tagen", such_config.veroeffentlicht_seit_tagen)
        return {"gefunden": 0, "veroeffentlicht": 0}

    producer = baue_producer(kafka_config)
    veroeffentlicht = veroeffentliche(producer, kafka_config.topic, anzeigen)
    log.info("%s Anzeigen nach %s geschrieben", veroeffentlicht, kafka_config.topic)

    return {"gefunden": len(anzeigen), "veroeffentlicht": veroeffentlicht}


def lambda_handler(event: Any, context: Any) -> dict[str, int]:
    """Von EventBridge aufgerufener Einstiegspunkt."""
    # Die Lambda-Laufzeit richtet den Root-Logger selbst ein, allerdings
    # auf WARNING. Ohne diese Zeile taucht keine der Info-Ausgaben in
    # CloudWatch auf, und ein Fehlschlag waere nicht nachvollziehbar.
    logging.getLogger().setLevel(logging.INFO)
    return run()


def main() -> int:
    """Lokaler Aufruf: python -m poller.main"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )
    try:
        ergebnis = run()
    except (ConfigError, JobsucheError) as exc:
        log.error("%s", exc)
        return 1

    print(json.dumps(ergebnis, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
