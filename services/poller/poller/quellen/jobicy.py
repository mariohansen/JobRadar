"""Jobicy - Boerse fuer entfernte Stellen, mit Regionsfilter.

Anders als Remote OK laesst sich die Region schon in der Anfrage
einschraenken, was die Trefferliste klein haelt. Abgefragt wird
Deutschland; Stellen ohne Ortsbindung sind darin enthalten.
"""
from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Iterator

from . import basis

log = logging.getLogger(__name__)

NAME = "jobicy"
BASIS_URL = "https://jobicy.com/api/v2/remote-jobs"

# Wie viele Anzeigen je Anfrage. Die Schnittstelle deckelt bei 50.
ANZAHL = 50

REGION = "germany"


def _uebersetze(job: dict[str, Any]) -> dict[str, Any] | None:
    branchen = job.get("jobIndustry")
    return basis.anzeige(
        quelle=NAME,
        kennung=job.get("id") or job.get("jobSlug") or "",
        titel=job.get("jobTitle") or "",
        firma=job.get("companyName") or "",
        orte=[job.get("jobGeo") or ""],
        beschreibung=basis.text_aus_html(
            job.get("jobDescription") or job.get("jobExcerpt")
        ),
        veroeffentlicht=job.get("pubDate"),
        url=job.get("url") or "",
        berufe=branchen if isinstance(branchen, list) else (),
        homeofficeprozent=100,
    )


def hole(config: Any) -> Iterator[dict[str, Any]]:
    parameter = urllib.parse.urlencode({"count": ANZAHL, "geo": REGION})
    antwort = basis.hole_json(BASIS_URL + "?" + parameter)
    for job in antwort.get("jobs") or []:
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
