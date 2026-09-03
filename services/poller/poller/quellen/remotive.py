"""Remotive - kuratierte Boerse fuer vollstaendig entfernte Stellen.

Deckt denselben Gedanken ab wie der zweite Durchgang bei der
Bundesagentur: Stellen, bei denen der Arbeitsort keine Rolle spielt.
Die Schnittstelle ist oeffentlich dokumentiert, kennt einen Suchparameter
und liefert den Anzeigentext mit.

Uebernommen wird nur, was von Deutschland aus zu erledigen ist. Das Feld
mit den zugelassenen Regionen entscheidet darueber - eine Stelle
"USA only" hilft hier nicht weiter.
"""
from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Iterator

from . import basis

log = logging.getLogger(__name__)

NAME = "remotive"
BASIS_URL = "https://remotive.com/api/remote-jobs"

# Regionen, aus denen sich eine Bewerbung aus Deutschland lohnt.
ERLAUBTE_REGIONEN = (
    "anywhere",
    "worldwide",
    "europe",
    "emea",
    "germany",
    "deutschland",
    "european union",
    "cet",
)


def _von_deutschland_aus(job: dict[str, Any]) -> bool:
    region = (job.get("candidate_required_location") or "").casefold()
    # Keine Angabe heisst hier: keine Einschraenkung.
    if not region:
        return True
    return any(erlaubt in region for erlaubt in ERLAUBTE_REGIONEN)


def _uebersetze(job: dict[str, Any]) -> dict[str, Any] | None:
    marken = job.get("tags")
    return basis.anzeige(
        quelle=NAME,
        kennung=job.get("id") or "",
        titel=job.get("title") or "",
        firma=job.get("company_name") or "",
        orte=[job.get("candidate_required_location") or ""],
        beschreibung=basis.text_aus_html(job.get("description")),
        veroeffentlicht=job.get("publication_date"),
        url=job.get("url") or "",
        berufe=marken if isinstance(marken, list) else (),
        # Remotive listet ausschliesslich vollstaendig entfernte Stellen.
        homeofficeprozent=100,
    )


def hole(config: Any) -> Iterator[dict[str, Any]]:
    for begriff in config.suchbegriffe:
        parameter = urllib.parse.urlencode({"search": begriff})
        antwort = basis.hole_json(BASIS_URL + "?" + parameter)
        for job in antwort.get("jobs") or []:
            if not _von_deutschland_aus(job):
                continue
            uebersetzt = _uebersetze(job)
            if uebersetzt is None:
                continue
            if not basis.im_zeitfenster(
                uebersetzt["datumErsteVeroeffentlichung"], config.veroeffentlicht_seit_tagen
            ):
                continue
            yield uebersetzt
