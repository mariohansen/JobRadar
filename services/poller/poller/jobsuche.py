"""Client fuer die Jobsuche-API der Bundesagentur fuer Arbeit.

Die API ist inoffiziell (siehe docs/adr/0001). Pfadversion und Feldnamen
koennen sich ohne Ankuendigung aendern, deshalb steht der Endpunkt an
genau einer Stelle und Fehler werden in einen eigenen Ausnahmetyp
uebersetzt, statt urllib-Interna nach oben durchzureichen.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterator

from .config import SearchConfig

log = logging.getLogger(__name__)

ENDPUNKT = "/pc/v6/jobs"

# Notbremse gegen eine Endlosschleife, falls die API bei hohen Seitenzahlen
# nicht wie erwartet eine leere Liste liefert.
MAX_SEITEN = 40

TIMEOUT_SEKUNDEN = 20


class JobsucheError(RuntimeError):
    """Die API war nicht erreichbar oder hat unerwartet geantwortet."""


def baue_url(
    config: SearchConfig, suchbegriff: str, seite: int, ortsgebunden: bool = True
) -> str:
    parameter = {
        "was": suchbegriff,
        # Begrenzt die Antwort auf kuerzlich veroeffentlichte Anzeigen.
        # Ohne diesen Filter liefert dieselbe Suche ein Vielfaches an
        # Treffern, die laengst bekannt sind.
        "veroeffentlichtseit": config.veroeffentlicht_seit_tagen,
        "size": config.seitengroesse,
        "page": seite,
    }

    # Ohne wo und umkreis sucht die API bundesweit. Das ist der Durchgang
    # fuer Stellen, bei denen der Arbeitsort keine Rolle spielt, weil sie
    # vollstaendig remote sind.
    if ortsgebunden:
        parameter["wo"] = config.ort
        parameter["umkreis"] = config.umkreis_km

    return f"{config.base_url}{ENDPUNKT}?{urllib.parse.urlencode(parameter)}"


def _hole(url: str, api_key: str) -> dict[str, Any]:
    anfrage = urllib.request.Request(url, headers={"X-API-Key": api_key})
    try:
        with urllib.request.urlopen(anfrage, timeout=TIMEOUT_SEKUNDEN) as antwort:
            return json.load(antwort)
    except urllib.error.HTTPError as exc:
        raise JobsucheError(f"HTTP {exc.code} von {url}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise JobsucheError(f"Keine Antwort von {url}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise JobsucheError(f"Antwort von {url} ist kein JSON: {exc}") from exc


def ist_vollstaendig_remote(job: dict[str, Any], min_prozent: int) -> bool:
    """Laesst sich die Stelle vollstaendig aus dem Homeoffice erledigen?

    Die API kennt drei Angaben: `homeofficemoeglich` als Ja/Nein,
    `homeofficetyp` mit den Werten NACH_VEREINBARUNG oder
    ANGABE_IN_PROZENT, und bei letzterem `homeofficeprozent` mit dem
    tatsaechlichen Anteil.

    Nur der Prozentwert ist belastbar. NACH_VEREINBARUNG heisst
    lediglich, dass darueber gesprochen werden kann - fuer eine Stelle am
    anderen Ende der Republik ist das keine Grundlage.
    """
    prozent = job.get("homeofficeprozent")
    if not isinstance(prozent, (int, float)):
        return False
    return prozent >= min_prozent


def suche(
    config: SearchConfig, suchbegriff: str, ortsgebunden: bool = True
) -> Iterator[dict[str, Any]]:
    """Liefert alle Treffer eines Suchbegriffs, Seite fuer Seite."""
    for seite in range(1, MAX_SEITEN + 1):
        daten = _hole(
            baue_url(config, suchbegriff, seite, ortsgebunden), config.api_key
        )
        treffer = daten.get("ergebnisliste") or []

        if not treffer:
            return

        yield from treffer

        # Eine nicht volle Seite ist die letzte - das erspart eine
        # zusaetzliche Anfrage, die garantiert leer zuruckkaeme.
        if len(treffer) < config.seitengroesse:
            return

    log.warning("Seitenlimit %s erreicht fuer %r - Rest wird ignoriert", MAX_SEITEN, suchbegriff)


def referenznummer(job: dict[str, Any]) -> str | None:
    """Eindeutige Kennung einer Anzeige.

    Hiess in der frueheren v4-Fassung der API noch 'refnr'. Steht deshalb
    an einer Stelle, statt im Code verteilt zu werden.
    """
    wert = job.get("referenznummer")
    return wert if isinstance(wert, str) and wert else None
