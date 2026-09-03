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
        """True, wenn diese Kennung noch nicht bekannt war."""
        return self._lege_an(
            {
                "referenznummer": referenznummer,
                "titel": titel,
                "erfasst_am": int(time.time()),
                # DynamoDB raeumt den Eintrag nach Ablauf selbst ab.
                "ablauf_zeitpunkt": int(time.time()) + self._aufbewahrung_sekunden,
                # Startzustand fuer den Bewerbungs-Tracker.
                "status": "GEFUNDEN",
            }
        )

    def ist_inhaltlich_neu(self, schluessel: str, referenznummer: str) -> bool:
        """True, wenn diese Stelle noch von keiner Quelle gemeldet wurde.

        `ist_neu` prueft die Kennung und greift damit nur innerhalb einer
        Quelle: dieselbe Stelle hat bei der Bundesagentur eine andere
        Referenznummer als auf Arbeitnow. Hier wird stattdessen ein
        Merkposten unter dem inhaltlichen Fingerabdruck angelegt -
        derselbe bedingte Schreibvorgang, nur ueber einen anderen
        Schluessel.

        Der Merkposten notiert, welche Anzeige zuerst da war. Das ist
        keine Verweiskette, sondern eine Spur fuer die Fehlersuche: wer
        wissen will, warum eine Anzeige nicht gemeldet wurde, findet hier
        die, die ihr zuvorgekommen ist.
        """
        return self._lege_an(
            {
                "referenznummer": schluessel,
                "zuerst_gesehen_als": referenznummer,
                "erfasst_am": int(time.time()),
                "ablauf_zeitpunkt": int(time.time()) + self._aufbewahrung_sekunden,
            }
        )

    def _lege_an(self, eintrag: dict) -> bool:
        """Bedingter Schreibvorgang: True, wenn der Schluessel neu war."""
        try:
            self._tabelle.put_item(
                Item=eintrag,
                ConditionExpression="attribute_not_exists(referenznummer)",
            )
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Kein Fehler, sondern die Antwort auf unsere Frage: der
                # Schluessel ist bereits vergeben.
                return False
            raise
