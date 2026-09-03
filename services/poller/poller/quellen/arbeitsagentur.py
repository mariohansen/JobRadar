"""Die Jobsuche der Bundesagentur - die urspruengliche und wichtigste Quelle.

Diese Datei uebersetzt nichts: die Anzeigen liegen bereits in dem Format
vor, das die uebrigen Quellen nachbilden. Sie fuegt nur die Herkunft
hinzu und kapselt die beiden Durchgaenge (Umkreis und bundesweit remote),
damit `main` alle Quellen gleich behandeln kann.

Die Referenznummer bleibt bewusst **ohne** Quellenpraefix. Sie ist der
Schluessel, unter dem Anzeigentexte im Archiv liegen, unter dem der
Tracker seine Zeilen wiederfindet und unter dem die Detailansicht
abgerufen wird - ein Praefix wuerde den vorhandenen Bestand entwerten.
"""
from __future__ import annotations

import logging
from typing import Any, Iterator

from ..jobsuche import ist_vollstaendig_remote, referenznummer, suche

log = logging.getLogger(__name__)

NAME = "arbeitsagentur"


def hole(config: Any) -> Iterator[dict[str, Any]]:
    for begriff in config.suchbegriffe:
        for job in suche(config, begriff):
            if referenznummer(job):
                job["quelle"] = NAME
                yield job

    if not config.remote_bundesweit:
        return

    # Zweiter Durchgang: ohne Ortsbindung, aber nur was vollstaendig aus
    # dem Homeoffice zu erledigen ist. Sonst waere der Suchraum ganz
    # Deutschland (ADR 0006).
    for begriff in config.suchbegriffe:
        for job in suche(config, begriff, ortsgebunden=False):
            if referenznummer(job) and ist_vollstaendig_remote(
                job, config.remote_min_prozent
            ):
                job["quelle"] = NAME
                yield job
