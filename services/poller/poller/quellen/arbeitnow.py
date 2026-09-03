"""Arbeitnow - deutsche Stellenboerse mit offener Schnittstelle.

Die wichtigste Ergaenzung zur Bundesagentur: derselbe Markt, aber
Anzeigen, die dort nicht gemeldet werden. Die Schnittstelle ist
ausdruecklich oeffentlich, liefert den Anzeigentext gleich mit und
verlangt keinen Schluessel.

Gefiltert wird hier statt in der Anfrage: die Schnittstelle kennt keine
Suchparameter, ihre Trefferliste ist der ganze Bestand, seitenweise.
"""
from __future__ import annotations

import logging
from typing import Any, Iterator

from . import basis

log = logging.getLogger(__name__)

NAME = "arbeitnow"
BASIS_URL = "https://www.arbeitnow.com/api/job-board-api"

# Der Bestand ist nach Datum sortiert, neueste zuerst. Mehr als ein paar
# Seiten zu lesen hiesse, in Anzeigen zu graben, die aelter sind als das
# Suchfenster - der Abbruch unten erledigt das von allein. Drei Seiten
# sind rund dreihundert Anzeigen und decken bei stuendlicher
# Aktualisierung mehrere Tage ab.
HOECHSTENS_SEITEN = 3


def _remoteanteil(job: dict[str, Any]) -> int | None:
    """100 wenn die Anzeige remote ist, sonst unbekannt.

    Das Feld kommt mal als echter Wahrheitswert, mal als Zeichenkette
    "True" - die Schnittstelle ist da nicht einheitlich.
    """
    wert = job.get("remote")
    if wert is True or (isinstance(wert, str) and wert.strip().casefold() == "true"):
        return 100
    return None


def _uebersetze(job: dict[str, Any]) -> dict[str, Any] | None:
    marken = job.get("tags")
    return basis.anzeige(
        quelle=NAME,
        kennung=job.get("slug") or "",
        titel=job.get("title") or "",
        firma=job.get("company_name") or "",
        orte=[job.get("location") or ""],
        beschreibung=basis.text_aus_html(job.get("description")),
        veroeffentlicht=job.get("created_at"),
        url=job.get("url") or "",
        berufe=marken if isinstance(marken, list) else (),
        homeofficeprozent=_remoteanteil(job),
    )


def _passt_zum_ort(job: dict[str, Any], ort: str) -> bool:
    """Im Umkreis gesucht - oder ueberall, wenn die Stelle remote ist."""
    if _remoteanteil(job) == 100:
        return True
    return ort.casefold() in (job.get("location") or "").casefold()


def hole(config: Any) -> Iterator[dict[str, Any]]:
    for seite in range(1, HOECHSTENS_SEITEN + 1):
        if seite > 1:
            basis.pause()
        try:
            antwort = basis.hole_json(BASIS_URL + "?page=" + str(seite))
        except basis.ZuVieleAnfragen as exc:
            # Was bis hier eingesammelt wurde, bleibt brauchbar.
            log.warning("%s bremst uns aus, Rest entfaellt: %s", NAME, exc)
            return
        treffer = antwort.get("data") or []
        if not treffer:
            return

        zu_alt = 0
        for job in treffer:
            uebersetzt = _uebersetze(job)
            if uebersetzt is None:
                continue
            if not basis.im_zeitfenster(
                uebersetzt["datumErsteVeroeffentlichung"], config.veroeffentlicht_seit_tagen
            ):
                zu_alt += 1
                continue
            if not basis.passt_zum_begriff(
                uebersetzt["stellenangebotsTitel"], config.suchbegriffe
            ):
                continue
            if not _passt_zum_ort(job, config.ort):
                continue
            yield uebersetzt

        # Nach Datum sortiert: ist eine ganze Seite aus dem Fenster
        # gefallen, sind es alle folgenden erst recht.
        if zu_alt == len(treffer):
            return
