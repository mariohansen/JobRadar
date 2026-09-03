"""Auswertung des Archivs: was der Markt verlangt, was davon fehlt.

Das Rohdatenarchiv haelt jede je gesehene Anzeige - auch die, die der
Filter aussortiert hat. Damit laesst sich beantworten, was in der Summe
gefragt ist, statt nur anzeigenweise zu vergleichen.

Der Nutzen liegt in der Verbindung mit dem Profil: nicht "Kafka steht in
vielen Anzeigen", sondern "Kafka fehlt dir in 34 der 91 Anzeigen, die
sonst gepasst haetten". Das eine ist eine Marktbeobachtung, das andere
eine Lernempfehlung.

Ausgewertet wird mit demselben Verzeichnis, das auch die Bewertung
benutzt - was dort nicht steht, taucht auch hier nicht auf.
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Iterable

from gemeinsam import anzeige, begriffe as bg, faehigkeiten as fk, passung

log = logging.getLogger(__name__)

# So viele Zeilen zeigt der Bericht je Abschnitt. Darunter wird die
# Datenlage duenn, darueber liest es niemand mehr.
HOECHSTENS = 20

# Unter so vielen Anzeigen ist ein Anteil keine Aussage.
MINDESTBESTAND = 10


@dataclass
class Auswertung:
    von: date | None = None
    bis: date | None = None
    anzeigen: int = 0
    bewertet: int = 0
    # Begriff -> in wie vielen Anzeigen er vorkommt.
    nachfrage: Counter = field(default_factory=Counter)
    # Begriff -> in wie vielen Anzeigen er verlangt wird und fehlt.
    luecken: Counter = field(default_factory=Counter)
    # Begriff -> in wie vielen Anzeigen er verlangt wird und da ist.
    abgedeckt: Counter = field(default_factory=Counter)
    # Monat ("2026-08") -> Begriff -> Anzahl.
    verlauf: dict[str, Counter] = field(default_factory=dict)
    stufen: Counter = field(default_factory=Counter)
    # Woerter, die wie eine Technologie aussehen und im Verzeichnis
    # fehlen. Der blinde Fleck der festen Liste, sichtbar gemacht.
    unbekannt: Counter = field(default_factory=Counter)

    def anteil(self, begriff: str) -> float:
        return self.nachfrage[begriff] / self.anzeigen if self.anzeigen else 0.0

    def _mit_anteil(self, zaehler: Counter, grenze: int) -> list[tuple[str, int, float]]:
        return [
            (begriff, anzahl, anzahl / self.anzeigen if self.anzeigen else 0.0)
            for begriff, anzahl in zaehler.most_common(grenze)
            if anzahl
        ]

    def wichtigste_luecken(self, grenze: int = HOECHSTENS) -> list[tuple[str, int, float]]:
        """Was am haeufigsten verlangt wird und im Profil fehlt."""
        return self._mit_anteil(self.luecken, grenze)

    def staerken(self, grenze: int = HOECHSTENS) -> list[tuple[str, int, float]]:
        """Gefragtes, das das Profil abdeckt."""
        return self._mit_anteil(self.abgedeckt, grenze)

    def fehlende_begriffe(self, grenze: int = HOECHSTENS) -> list[tuple[str, int, float]]:
        """Haeufige Kandidaten, die das Verzeichnis noch nicht kennt.

        Was hier oben steht, gehoert vermutlich nach faehigkeiten.py -
        sonst bleibt es fuer Bewertung und Trend unsichtbar.
        """
        return self._mit_anteil(self.unbekannt, grenze)

    def aussagekraeftig(self) -> bool:
        return self.anzeigen >= MINDESTBESTAND

    def monate(self) -> list[str]:
        return sorted(self.verlauf)


def werte_aus(
    anzeigen: Iterable[tuple[date, dict[str, Any]]],
    profil: Any = None,
    detail_zu: Callable[[str], dict[str, Any] | None] | None = None,
    fortschritt: Callable[[int], None] | None = None,
) -> Auswertung:
    """Zaehlt Begriffe ueber den Bestand.

    Gezaehlt wird je Anzeige, nicht je Nennung: eine Anzeige, die Java
    zwoelfmal schreibt, ist eine Anzeige, die Java verlangt.
    """
    ergebnis = Auswertung()
    # Einmal aufbauen statt je Anzeige.
    bekannt = {name.casefold() for name in fk.KATEGORIE_VON}

    for laufend, (tag, job) in enumerate(anzeigen, start=1):
        if fortschritt:
            fortschritt(laufend)

        detail = {}
        if detail_zu is not None:
            referenz = job.get("referenznummer")
            if isinstance(referenz, str) and referenz:
                detail = detail_zu(referenz) or {}

        text = anzeige.text(job, detail)
        begriffe = set(fk.finde(text))
        # Nur wo es einen Anzeigentext gibt - Titel und Berufsbezeichnung
        # allein liefern keine brauchbaren Kandidaten.
        beschreibung = anzeige.beschreibung(detail, job)
        if beschreibung:
            ergebnis.unbekannt.update(bg.kandidaten(beschreibung, bekannt))

        ergebnis.anzeigen += 1
        ergebnis.von = tag if ergebnis.von is None else min(ergebnis.von, tag)
        ergebnis.bis = tag if ergebnis.bis is None else max(ergebnis.bis, tag)
        ergebnis.nachfrage.update(begriffe)

        monat = f"{tag:%Y-%m}"
        ergebnis.verlauf.setdefault(monat, Counter()).update(begriffe)

        if profil is not None:
            ergebnis.luecken.update(begriffe - profil.alle)
            ergebnis.abgedeckt.update(begriffe & profil.alle)

            bewertung = passung.bewerte(profil, anzeige.titel(job), text)
            ergebnis.stufen[bewertung.stufe] += 1
            if bewertung.brauchbar:
                ergebnis.bewertet += 1

    return ergebnis
