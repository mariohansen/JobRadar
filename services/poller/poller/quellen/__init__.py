"""Verzeichnis der Stellenquellen.

Jede Quelle ist ein Modul mit einer Funktion `hole(config)`, die
Anzeigen im Format der Jobsuche-API liefert (siehe `basis`). Wer eine
weitere hinzufuegen will, schreibt eine Datei und traegt sie hier ein -
mehr beruehrt es nicht.

Zur Auswahl steht sie ueber die Umgebungsvariable `POLLER_QUELLEN`.
Voreingestellt sind die beiden mit deutschem Bestand; die Boersen fuer
entfernte Stellen sind zuschaltbar, weil sie einen weltweiten Markt
abbilden und die Trefferliste schnell aufblaehen.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Iterator

from . import adzuna, arbeitnow, arbeitsagentur, basis, jobicy, remoteok, remotive

log = logging.getLogger(__name__)

QuellenFehler = basis.QuellenFehler

# Name -> Modul. Die Reihenfolge bestimmt, welche Fassung einer doppelt
# gelisteten Anzeige gewinnt: die zuerst gelesene. Die Bundesagentur
# steht deshalb vorn - ihre Datensaetze sind die vollstaendigsten und
# ihre Referenznummer ist die, an der Archiv und Tracker haengen.
VERZEICHNIS: dict[str, Any] = {
    arbeitsagentur.NAME: arbeitsagentur,
    arbeitnow.NAME: arbeitnow,
    adzuna.NAME: adzuna,
    remotive.NAME: remotive,
    remoteok.NAME: remoteok,
    jobicy.NAME: jobicy,
}

VORGABE: tuple[str, ...] = (arbeitsagentur.NAME, arbeitnow.NAME, adzuna.NAME)

ALLE: tuple[str, ...] = tuple(VERZEICHNIS)


class UnbekannteQuelle(ValueError):
    """Ein Name, den das Verzeichnis nicht kennt."""


def pruefe(namen: tuple[str, ...]) -> tuple[str, ...]:
    unbekannt = [name for name in namen if name not in VERZEICHNIS]
    if unbekannt:
        raise UnbekannteQuelle(
            f"Unbekannte Quelle(n): {', '.join(unbekannt)}. "
            f"Bekannt sind: {', '.join(ALLE)}"
        )
    return namen


def ist_verfuegbar(name: str) -> bool:
    """Kann diese Quelle gerade abgefragt werden?

    Nur Adzuna braucht Zugangsdaten. Fehlen sie, wird die Quelle
    uebersprungen statt den Lauf mit einem Fehler zu beenden - so laesst
    sie sich in der Vorgabe stehen lassen, ohne dass jeder sich
    registrieren muss.
    """
    pruefung: Callable[[], bool] | None = getattr(
        VERZEICHNIS[name], "ist_verfuegbar", None
    )
    return pruefung() if pruefung else True


def hole(name: str, config: Any) -> Iterator[dict[str, Any]]:
    return VERZEICHNIS[name].hole(config)
