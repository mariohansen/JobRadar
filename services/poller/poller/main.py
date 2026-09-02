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

from .config import ConfigError, KafkaConfig, SearchConfig
from .jobsuche import (
    JobsucheError,
    ist_vollstaendig_remote,
    referenznummer,
    suche,
)
from .publisher import baue_producer, veroeffentliche

log = logging.getLogger(__name__)


def sammle_anzeigen(config: SearchConfig) -> list[dict[str, Any]]:
    """Treffer aller Suchbegriffe aus zwei Durchgaengen, ohne Doppelte.

    Der erste Durchgang sucht im Umkreis des Wohnorts, unabhaengig davon,
    ob Homeoffice angeboten wird. Der zweite sucht bundesweit und nimmt
    nur Stellen mit, die vollstaendig remote zu erledigen sind - dort ist
    die Entfernung gleichgueltig.

    Doppelte innerhalb eines Laufs entstehen auf zwei Wegen: dieselbe
    Anzeige unter zwei Suchbegriffen, oder eine Hamburger Stelle, die
    zugleich vollstaendig remote ist. Beides faengt `gesehen` ab. Das
    ersetzt keine Deduplizierung gegenueber frueheren Laeufen, dafuer ist
    der filter-dedup-Consumer zustaendig.
    """
    gesehen: set[str] = set()
    anzeigen: list[dict[str, Any]] = []

    def aufnehmen(job: dict[str, Any]) -> bool:
        nummer = referenznummer(job)
        if nummer is None or nummer in gesehen:
            return False
        gesehen.add(nummer)
        anzeigen.append(job)
        return True

    for begriff in config.suchbegriffe:
        anzahl = sum(1 for job in suche(config, begriff) if aufnehmen(job))
        log.info("%r im Umkreis von %s: %s Anzeigen", begriff, config.ort, anzahl)

    if not config.remote_bundesweit:
        return anzeigen

    for begriff in config.suchbegriffe:
        anzahl = sum(
            1
            for job in suche(config, begriff, ortsgebunden=False)
            if ist_vollstaendig_remote(job, config.remote_min_prozent)
            and aufnehmen(job)
        )
        log.info(
            "%r bundesweit mit mindestens %s Prozent Homeoffice: %s Anzeigen",
            begriff, config.remote_min_prozent, anzahl,
        )

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
