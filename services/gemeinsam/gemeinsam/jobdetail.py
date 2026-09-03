"""Client fuer die Detailansicht einer Stellenanzeige.

Die Trefferliste der Jobsuche enthaelt keinen Anzeigentext (ADR 0001).
Ansprechpartner, Kontaktdaten und eine etwaige Verguetungsangabe stehen
nur in der Detailansicht, die je Anzeige einzeln abgerufen werden muss.

Die Referenznummer steht base64-kodiert im Pfad. Das Gleichheitszeichen
der Auffuellung bleibt dabei unkodiert - es ist in einem Pfadsegment
zulaessig, und die Schnittstelle erwartet es so.
"""
from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger(__name__)

BASIS_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
ENDPUNKT = "/pc/v4/jobdetails"

# Dieselbe oeffentlich bekannte clientId wie beim Poller. Kein Geheimnis.
API_KEY = "jobboerse-jobsuche"

TIMEOUT_SEKUNDEN = 20


class JobdetailError(RuntimeError):
    """Die Schnittstelle war nicht erreichbar oder antwortete unerwartet."""


def kodiere(referenznummer: str) -> str:
    return base64.b64encode(referenznummer.encode("utf-8")).decode("ascii")


def baue_url(referenznummer: str) -> str:
    return f"{BASIS_URL}{ENDPUNKT}/{kodiere(referenznummer)}"


def hole(referenznummer: str, oeffner=urllib.request.urlopen) -> dict[str, Any] | None:
    """Detailansicht einer Anzeige, oder None wenn es sie nicht mehr gibt.

    Zurueckgezogene Anzeigen beantwortet die Schnittstelle mit 404. Das
    ist beim Export der Normalfall - das Archiv reicht 180 Tage zurueck,
    eine Anzeige lebt selten so lange - und deshalb kein Fehler.
    """
    url = baue_url(referenznummer)
    anfrage = urllib.request.Request(url, headers={"X-API-Key": API_KEY})
    try:
        with oeffner(anfrage, timeout=TIMEOUT_SEKUNDEN) as antwort:
            return json.load(antwort)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            log.info("Anzeige %s ist nicht mehr abrufbar", referenznummer)
            return None
        raise JobdetailError(f"HTTP {exc.code} fuer {referenznummer}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise JobdetailError(f"Keine Antwort fuer {referenznummer}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise JobdetailError(f"Antwort fuer {referenznummer} ist kein JSON: {exc}") from exc
