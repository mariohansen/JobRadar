"""Client fuer den Entgeltatlas der Bundesagentur fuer Arbeit.

Wie die Jobsuche ist auch diese Schnittstelle inoffiziell. Die in
bundesAPI/entgeltatlas-api dokumentierte clientId wird inzwischen
abgewiesen; gueltig ist die, die die Weboberflaeche selbst verwendet.

Abgefragt wird nach KldB-Schluessel (Klassifikation der Berufe 2010).
Die fuenfte Ziffer steht fuer das Anforderungsniveau: 1 Helfer,
2 Fachkraft, 3 Spezialist, 4 Experte.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

BASIS_URL = "https://rest.arbeitsagentur.de/infosysbub/entgeltatlas/pc/v1/entgelte"
API_KEY = "infosysbub-ega"
TIMEOUT_SEKUNDEN = 20

# Die Regionskennung aus der Antwort der Schnittstelle.
REGION_DEUTSCHLAND = 1
REGION_HAMBURG = 5

# "Gesamt" in den uebrigen Dimensionen - ohne diese Einschraenkung
# liefert die Antwort mehrere hundert Kombinationen aus Branche, Alter
# und Geschlecht.
GESAMT = 1


class EntgeltatlasError(RuntimeError):
    """Die Schnittstelle war nicht erreichbar oder antwortete unerwartet."""


@dataclass(frozen=True)
class Entgelt:
    kldb: str
    niveau: str
    region: str
    median: int
    q25: int
    q75: int
    fallzahl: int


def _ist_angegeben(wert: Any) -> bool:
    """Die Schnittstelle nutzt negative Zahlen als Platzhalter.

    -1 steht fuer "keine Daten", -2 fuer "nicht ausweisbar", und bei der
    Fallzahl erscheint -42. Wer diese Werte als Betrag verwendet, erhaelt
    negative Gehaelter.
    """
    return isinstance(wert, int) and wert >= 0


def hole_rohdaten(kldb: str) -> list[dict[str, Any]]:
    url = f"{BASIS_URL}/{urllib.parse.quote(kldb)}"
    anfrage = urllib.request.Request(url, headers={"X-API-Key": API_KEY})
    try:
        with urllib.request.urlopen(anfrage, timeout=TIMEOUT_SEKUNDEN) as antwort:
            return json.load(antwort)
    except urllib.error.HTTPError as exc:
        raise EntgeltatlasError(f"HTTP {exc.code} fuer KldB {kldb}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise EntgeltatlasError(f"Keine Antwort fuer KldB {kldb}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EntgeltatlasError(f"Antwort fuer KldB {kldb} ist kein JSON: {exc}") from exc


def waehle_gesamtwert(
    datensaetze: list[dict[str, Any]], region_id: int
) -> dict[str, Any] | None:
    """Der eine Datensatz ohne Aufschluesselung nach Branche, Alter, Geschlecht."""
    for eintrag in datensaetze:
        if (
            eintrag.get("region", {}).get("id") == region_id
            and eintrag.get("branche", {}).get("id") == GESAMT
            and eintrag.get("ageCategory", {}).get("id") == GESAMT
            and eintrag.get("gender", {}).get("id") == GESAMT
        ):
            return eintrag
    return None


def entgelt(kldb: str, region_id: int = REGION_HAMBURG) -> Entgelt | None:
    """Monatliches Bruttoentgelt fuer einen Beruf, oder None ohne Datenlage."""
    eintrag = waehle_gesamtwert(hole_rohdaten(kldb), region_id)
    if eintrag is None:
        return None

    if not _ist_angegeben(eintrag.get("entgelt")):
        log.info("Fuer KldB %s liegen in dieser Region keine Werte vor", kldb)
        return None

    return Entgelt(
        kldb=kldb,
        niveau=eintrag.get("performanceLevel", {}).get("bezeichnung", "unbekannt"),
        region=eintrag.get("region", {}).get("bezeichnung", "unbekannt"),
        median=eintrag["entgelt"],
        # Die Quartile koennen einzeln fehlen, auch wenn der Median
        # vorliegt - dann 0 statt einer negativen Zahl.
        q25=eintrag["entgeltQ25"] if _ist_angegeben(eintrag.get("entgeltQ25")) else 0,
        q75=eintrag["entgeltQ75"] if _ist_angegeben(eintrag.get("entgeltQ75")) else 0,
        fallzahl=eintrag["besetzung"] if _ist_angegeben(eintrag.get("besetzung")) else 0,
    )
