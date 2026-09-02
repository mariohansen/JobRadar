"""Versand ueber SES."""
from __future__ import annotations

import logging
from typing import Any

import boto3

from . import mail

log = logging.getLogger(__name__)


class Versand:
    def __init__(self, absender: str, empfaenger: str) -> None:
        self._ses = boto3.client("ses")
        self._absender = absender
        self._empfaenger = empfaenger

    def sende(self, anzeigen: list[dict[str, Any]]) -> str:
        """Verschickt einen Stapel und gibt die Nachrichtenkennung zurueck."""
        antwort = self._ses.send_email(
            # Immer dieselbe Absenderadresse, damit sich beim Mailanbieter
            # eine Reputation aufbauen kann.
            Source=self._absender,
            Destination={"ToAddresses": [self._empfaenger]},
            Message={
                "Subject": {"Data": mail.betreff(anzeigen), "Charset": "UTF-8"},
                "Body": {
                    # Beide Teile: Mailprogramme ohne HTML-Darstellung
                    # zeigen den Textteil, und Spamfilter bewerten das
                    # Vorhandensein positiv.
                    "Text": {"Data": mail.als_text(anzeigen), "Charset": "UTF-8"},
                    "Html": {"Data": mail.als_html(anzeigen), "Charset": "UTF-8"},
                },
            },
        )
        return antwort["MessageId"]
