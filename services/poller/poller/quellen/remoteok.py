"""Remote OK - grosse Boerse fuer entfernte Stellen, vor allem IT.

Die Schnittstelle liefert den gesamten aktuellen Bestand als eine Liste.
Ihr erster Eintrag ist ein Hinweis auf die Nutzungsbedingungen und keine
Anzeige; erkennbar daran, dass ihm die Stellenbezeichnung fehlt.

Remote OK bittet um einen Rueckverweis auf die Anzeige. Den traegt die
Tabelle ohnehin in der Spalte "Link zur Ausschreibung", und die Mail
verlinkt ebenfalls dorthin.
"""
from __future__ import annotations

import logging
from typing import Any, Iterator

from . import basis

log = logging.getLogger(__name__)

NAME = "remoteok"
BASIS_URL = "https://remoteok.com/api"


def _uebersetze(job: dict[str, Any]) -> dict[str, Any] | None:
    marken = job.get("tags")
    return basis.anzeige(
        quelle=NAME,
        kennung=job.get("id") or job.get("slug") or "",
        titel=job.get("position") or "",
        firma=job.get("company") or "",
        orte=[job.get("location") or ""],
        beschreibung=basis.text_aus_html(job.get("description")),
        veroeffentlicht=job.get("date") or job.get("epoch"),
        url=job.get("url") or job.get("apply_url") or "",
        berufe=marken if isinstance(marken, list) else (),
        homeofficeprozent=100,
    )


def hole(config: Any) -> Iterator[dict[str, Any]]:
    for job in basis.hole_json(BASIS_URL):
        # Der Hinweiskopf traegt keine Stellenbezeichnung.
        if not isinstance(job, dict) or not job.get("position"):
            continue
        uebersetzt = _uebersetze(job)
        if uebersetzt is None:
            continue
        if not basis.im_zeitfenster(
            uebersetzt["datumErsteVeroeffentlichung"], config.veroeffentlicht_seit_tagen
        ):
            continue
        if not basis.passt_zum_begriff(
            uebersetzt["stellenangebotsTitel"], config.suchbegriffe
        ):
            continue
        yield uebersetzt
