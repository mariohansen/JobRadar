"""Adzuna - Aggregator mit breiter deutscher Abdeckung.

Die einzige Quelle hier, die Zugangsdaten braucht: eine kostenlose
Registrierung liefert `app_id` und `app_key`. Fehlen sie, meldet sich
diese Quelle gar nicht erst zum Dienst - siehe `ist_verfuegbar`.

Adzuna sammelt aus vielen Portalen und liefert deshalb absehbar Anzeigen,
die auch anderswo stehen. Genau dafuer gibt es den inhaltlichen
Fingerabdruck im filter-dedup.

Die Trefferliste enthaelt nur einen Auszug des Anzeigentextes. Das reicht
fuer die Passungsbewertung meist nicht, ist aber besser als nichts - und
der Auszug nennt die geforderten Techniken erfahrungsgemaess zuerst.
"""
from __future__ import annotations

import logging
import os
import urllib.parse
from typing import Any, Iterator

from . import basis

log = logging.getLogger(__name__)

NAME = "adzuna"
BASIS_URL = "https://api.adzuna.com/v1/api/jobs"

LAND = "de"
JE_SEITE = 50
HOECHSTENS_SEITEN = 3


def zugangsdaten() -> tuple[str, str]:
    return (
        os.environ.get("ADZUNA_APP_ID", "").strip(),
        os.environ.get("ADZUNA_APP_KEY", "").strip(),
    )


def ist_verfuegbar() -> bool:
    """Ohne Schluessel bleibt diese Quelle still statt zu scheitern."""
    kennung, schluessel = zugangsdaten()
    return bool(kennung and schluessel)


def _uebersetze(job: dict[str, Any]) -> dict[str, Any] | None:
    ort = job.get("location") or {}
    bezeichnung = ort.get("display_name") if isinstance(ort, dict) else ""
    firma = job.get("company") or {}
    kategorie = job.get("category") or {}
    return basis.anzeige(
        quelle=NAME,
        kennung=job.get("id") or "",
        titel=job.get("title") or "",
        firma=firma.get("display_name", "") if isinstance(firma, dict) else "",
        orte=[bezeichnung or ""],
        beschreibung=basis.text_aus_html(job.get("description")),
        veroeffentlicht=job.get("created"),
        url=job.get("redirect_url") or "",
        berufe=[kategorie.get("label", "")] if isinstance(kategorie, dict) else (),
    )


def hole(config: Any) -> Iterator[dict[str, Any]]:
    kennung, schluessel = zugangsdaten()
    if not (kennung and schluessel):
        return

    for begriff in config.suchbegriffe:
        for seite in range(1, HOECHSTENS_SEITEN + 1):
            parameter = urllib.parse.urlencode(
                {
                    "app_id": kennung,
                    "app_key": schluessel,
                    "results_per_page": JE_SEITE,
                    "what": begriff,
                    "where": config.ort,
                    "distance": config.umkreis_km,
                    "max_days_old": config.veroeffentlicht_seit_tagen,
                    "content-type": "application/json",
                }
            )
            if seite > 1:
                basis.pause()
            try:
                antwort = basis.hole_json(
                    f"{BASIS_URL}/{LAND}/search/{seite}?{parameter}"
                )
            except basis.ZuVieleAnfragen as exc:
                log.warning("%s bremst uns aus, Rest entfaellt: %s", NAME, exc)
                return
            treffer = antwort.get("results") or []
            if not treffer:
                return

            for job in treffer:
                uebersetzt = _uebersetze(job)
                if uebersetzt is not None:
                    yield uebersetzt

            if len(treffer) < JE_SEITE:
                break
