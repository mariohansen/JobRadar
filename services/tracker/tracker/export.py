"""Beschaffung der Daten, aus denen die Tracker-Tabelle entsteht.

Der Tabelleneintrag aus DynamoDB nennt nur Referenz, Titel und Status.
Alles Weitere liegt woanders: die Anzeige selbst im Rohdatenarchiv, ihr
Text in der Detailansicht der Jobsuche.

Die Detailansicht wird je Anzeige genau einmal geholt und danach im
Archiv abgelegt. Ein zweiter Export belastet die Schnittstelle also
nicht erneut - dieselbe Zurueckhaltung, aus der auch der Poller nur alle
zehn Stunden laeuft.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Iterable

from gemeinsam import anzeige, passung
from gemeinsam.jobdetail import JobdetailError, hole as hole_detail

from gemeinsam.archiv import Archiv

from . import felder

log = logging.getLogger(__name__)

# Muss zu felder.QUELLE_ARBEITSAGENTUR passen; hier noch einmal genannt,
# damit Quellen ohne Import der Spaltenlogik auskommt.
QUELLE_ARBEITSAGENTUR = "arbeitsagentur"


# Kurze Pause zwischen zwei Abrufen. Die Schnittstelle ist inoffiziell
# und ohne Zusage; ein Export ueber hundert Anzeigen soll nicht wie ein
# Lasttest aussehen.
PAUSE_SEKUNDEN = 0.3


def _text(wert: Any) -> str:
    return wert.strip() if isinstance(wert, str) else ""


class Quellen:
    """Liefert Rohdaten und Detailansicht zu einem Tabelleneintrag."""

    def __init__(
        self,
        archiv: Archiv | None,
        mit_details: bool = True,
        details_erneuern: bool = False,
        abruf: Callable[[str], dict[str, Any] | None] = hole_detail,
    ) -> None:
        self._archiv = archiv
        self._mit_details = mit_details and archiv is not None
        self._details_erneuern = details_erneuern
        self._abruf = abruf

    def rohdaten(self, eintrag: Any) -> dict[str, Any]:
        if self._archiv is None:
            return {}
        return self._archiv.rohdaten(eintrag.referenznummer, eintrag.erfasst_am) or {}

    def detail(self, eintrag: Any, roh: dict[str, Any] | None = None) -> dict[str, Any]:
        """Detailansicht zur Anzeige - nur wo es eine gibt und sie fehlt.

        Die Detailansicht gehoert zur Jobsuche der Bundesagentur. Die
        uebrigen Quellen liefern ihren Text schon in der Trefferliste;
        deren Referenznummer wuerde dort nur ins Leere laufen.
        """
        if not self._mit_details:
            return {}

        roh = roh or {}
        if anzeige.beschreibung(roh):
            return {}
        if _text(roh.get("quelle")) not in ("", QUELLE_ARBEITSAGENTUR):
            return {}

        referenz = eintrag.referenznummer
        if not self._details_erneuern:
            gecacht = self._archiv.detail(referenz)
            if gecacht is not None:
                return gecacht

        try:
            frisch = self._abruf(referenz)
        except JobdetailError as exc:
            # Eine unerreichbare Anzeige darf den Export nicht abbrechen.
            log.warning("%s", exc)
            return {}

        # Auch das leere Ergebnis einer zurueckgezogenen Anzeige wird
        # gemerkt, sonst fragt jeder weitere Export erneut nach.
        frisch = frisch or {}
        self._archiv.merke_detail(referenz, frisch)
        time.sleep(PAUSE_SEKUNDEN)
        return frisch


def baue_zeilen(
    eintraege: Iterable[Any],
    quellen: Quellen,
    fortschritt: Callable[[int, int], None] | None = None,
    profil: Any = None,
) -> list[dict[str, Any]]:
    eintraege = list(eintraege)
    zeilen = []
    for laufend, eintrag in enumerate(eintraege, start=1):
        if fortschritt:
            fortschritt(laufend, len(eintraege))
        roh = quellen.rohdaten(eintrag)
        detail = quellen.detail(eintrag, roh)
        titel = roh.get("stellenangebotsTitel") or eintrag.titel
        bewertung = (
            passung.bewerte(profil, titel, anzeige.text(roh, detail))
            if profil is not None
            else None
        )
        zeilen.append(felder.zeile(eintrag, roh, detail, bewertung))
    return zeilen
