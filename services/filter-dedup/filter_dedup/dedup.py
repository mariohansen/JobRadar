"""Deduplizierung gegen DynamoDB.

Der Kern ist ein bedingter Schreibvorgang: statt erst zu fragen, ob eine
Anzeige bekannt ist, und dann zu schreiben, wird in einem Schritt
geschrieben - unter der Bedingung, dass der Schluessel noch nicht
existiert. Schlaegt die Bedingung fehl, war die Anzeige schon da.

Der naheliegende Weg ueber GetItem und danach PutItem hat eine Luecke:
zwischen Lesen und Schreiben kann ein zweiter Consumer denselben
Schluessel anlegen, und beide halten die Anzeige fuer neu. Der bedingte
Schreibvorgang ist dagegen atomar.
"""
from __future__ import annotations

import logging
import time

import boto3
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)


class Dedup:
    def __init__(self, tabellenname: str, aufbewahrung_tage: int) -> None:
        self._tabelle = boto3.resource("dynamodb").Table(tabellenname)
        self._aufbewahrung_sekunden = aufbewahrung_tage * 24 * 3600

    def ist_neu(self, referenznummer: str, titel: str = "") -> bool:
        """True, wenn die Anzeige noch nicht bekannt war."""
        try:
            self._tabelle.put_item(
                Item={
                    "referenznummer": referenznummer,
                    "titel": titel,
                    "erfasst_am": int(time.time()),
                    # DynamoDB raeumt den Eintrag nach Ablauf selbst ab.
                    "ablauf_zeitpunkt": int(time.time()) + self._aufbewahrung_sekunden,
                    # Startzustand fuer den Bewerbungs-Tracker.
                    "status": "GEFUNDEN",
                },
                ConditionExpression="attribute_not_exists(referenznummer)",
            )
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Kein Fehler, sondern die Antwort auf unsere Frage: die
                # Anzeige ist bereits erfasst.
                return False
            raise
