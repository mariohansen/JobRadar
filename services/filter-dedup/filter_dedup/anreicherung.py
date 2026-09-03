"""Anreicherung neuer Anzeigen um Text, Bewertung und Randdaten.

Die Trefferliste der Jobsuche enthaelt keinen Anzeigentext (ADR 0001).
Ohne ihn laesst sich weder die Passung zum eigenen Profil bestimmen noch
in der Mail etwas Nuetzlicheres zeigen als Titel und Ort.

Warum hier und nicht im notifier:

* Geholt wird der Text nur fuer Anzeigen, die Dedup und Filter passiert
  haben - also einmal je wirklich neuer Anzeige, nicht einmal je
  Nachricht.
* Das Ergebnis landet im selben S3-Zwischenspeicher, aus dem sich spaeter
  der Export bedient. Der muss dann gar nichts mehr abrufen.
* Der notifier bleibt reiner Formatierer und braucht weder Profil noch
  Netzzugriff.

Abgerufen wird nur, was noetig ist: die Trefferliste der Bundesagentur
kommt ohne Text, die der uebrigen Quellen bringt ihn mit. Wo er schon
dasteht, entfaellt der Abruf.

Nichts davon darf die Pipeline aufhalten. Faellt die Detailansicht aus,
geht die Anzeige ohne Anreicherung weiter - eine Mail ohne Bewertung ist
besser als keine Mail.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from gemeinsam import anzeige, passung
from gemeinsam.jobdetail import JobdetailError, hole as hole_detail

log = logging.getLogger(__name__)

# Unter diesem Schluessel haengt alles, was nicht von der Schnittstelle
# stammt, sondern von uns. Ein eigener Namensraum haelt die Anzeige
# selbst unveraendert - und im Archiv landet sie ohnehin vorher.
SCHLUESSEL = "jobradar"


class Anreicherung:
    def __init__(
        self,
        archiv,
        profil: Any = None,
        mit_details: bool = True,
        abruf: Callable[[str], dict[str, Any] | None] = hole_detail,
    ) -> None:
        self._archiv = archiv
        self._profil = profil
        self._mit_details = mit_details
        self._abruf = abruf

    def _detail(self, job: dict[str, Any], referenznummer: str) -> dict[str, Any]:
        if not self._mit_details:
            return {}

        # Nur die Bundesagentur liefert ihre Trefferliste ohne Text. Die
        # uebrigen Quellen bringen ihn mit - fuer die gibt es weder eine
        # Detailansicht noch eine Referenznummer, unter der man sie
        # abrufen koennte.
        if anzeige.beschreibung(job):
            return {}

        gecacht = self._archiv.detail(referenznummer)
        if gecacht is not None:
            return gecacht

        try:
            frisch = self._abruf(referenznummer) or {}
        except JobdetailError as exc:
            log.warning("Kein Anzeigentext fuer %s: %s", referenznummer, exc)
            return {}

        try:
            self._archiv.merke_detail(referenznummer, frisch)
        except Exception as exc:  # S3 kann kurzzeitig ausfallen
            log.warning("Anzeigentext zu %s nicht gemerkt: %s", referenznummer, exc)

        return frisch

    def ergaenze(self, job: dict[str, Any], referenznummer: str) -> dict[str, Any]:
        """Haengt den Zusatz an die Anzeige und gibt ihn zurueck."""
        detail = self._detail(job, referenznummer)

        zusatz: dict[str, Any] = {
            "alter_tage": anzeige.alter_tage(job),
            "entfernung_km": anzeige.entfernung_km(job),
        }

        if self._profil is not None:
            bewertung = passung.bewerte(
                self._profil, anzeige.titel(job), anzeige.text(job, detail)
            )
            zusatz.update(
                stufe=bewertung.stufe,
                punkte=bewertung.punkte if bewertung.brauchbar else None,
                treffer=list(bewertung.treffer),
                luecken=list(bewertung.luecken),
                schwerpunkte=[t for t in bewertung.treffer if t in bewertung.schwerpunkte],
            )

        job[SCHLUESSEL] = zusatz
        return zusatz


def sicher_ergaenzen(anreicherung: Anreicherung | None, job: dict[str, Any], referenznummer: str) -> None:
    """Anreichern, aber niemals auf Kosten der Zustellung.

    Ein Fehler in dieser Stufe ist aergerlich, aber kein Grund, eine neue
    Anzeige nicht zu melden. Deshalb faengt diese Huelle alles ab, was
    unterwegs schiefgehen kann.
    """
    if anreicherung is None:
        return
    try:
        anreicherung.ergaenze(job, referenznummer)
    except Exception as exc:
        log.warning("Anreicherung von %s uebersprungen: %s", referenznummer, exc)
