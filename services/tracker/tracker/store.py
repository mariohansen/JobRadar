"""Zugriff auf die Bewerbungsdaten in DynamoDB.

Der Tracker nutzt dieselbe Tabelle wie die Deduplizierung. Eine zweite
waere nicht nur zusaetzlicher Aufwand, sondern muesste auch staendig mit
der ersten abgeglichen werden - der Dedup-Schritt legt bereits jede
gefundene Anzeige mit dem Status GEFUNDEN an.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterator

import boto3
from botocore.exceptions import ClientError

from gemeinsam import fingerabdruck

from . import status as st


class UnbekannteAnzeige(LookupError):
    """Zu dieser Referenznummer gibt es keinen Eintrag."""


@dataclass(frozen=True)
class Eintrag:
    referenznummer: str
    titel: str
    status: str
    erfasst_am: int
    geaendert_am: int | None

    @classmethod
    def aus_item(cls, item: dict[str, Any]) -> "Eintrag":
        return cls(
            referenznummer=item["referenznummer"],
            titel=item.get("titel") or "",
            status=item.get("status") or st.GEFUNDEN,
            erfasst_am=int(item.get("erfasst_am") or 0),
            geaendert_am=int(item["geaendert_am"]) if item.get("geaendert_am") else None,
        )


class Store:
    def __init__(self, tabellenname: str) -> None:
        self._tabelle = boto3.resource("dynamodb").Table(tabellenname)

    def hole(self, referenznummer: str) -> Eintrag:
        antwort = self._tabelle.get_item(Key={"referenznummer": referenznummer})
        if "Item" not in antwort:
            raise UnbekannteAnzeige(referenznummer)
        return Eintrag.aus_item(antwort["Item"])

    def liste(self, nur_status: str | None = None) -> Iterator[Eintrag]:
        """Alle Eintraege, optional auf einen Status eingeschraenkt.

        Verwendet Scan, liest also die gesamte Tabelle. Bei einigen
        hundert Anzeigen ist das unproblematisch und spart einen
        zusaetzlichen Index; bei sehr grossen Bestaenden waere ein
        globaler Sekundaerindex auf den Status der richtige Weg.

        Uebersprungen werden die Merkposten, die der filter-dedup fuer
        den quellenuebergreifenden Abgleich anlegt: sie stehen in
        derselben Tabelle, sind aber keine Anzeigen.
        """
        argumente: dict[str, Any] = {}
        if nur_status:
            # status ist in DynamoDB ein reserviertes Wort und braucht
            # deshalb einen Platzhalter.
            argumente = {
                "FilterExpression": "#s = :s",
                "ExpressionAttributeNames": {"#s": "status"},
                "ExpressionAttributeValues": {":s": nur_status},
            }

        while True:
            antwort = self._tabelle.scan(**argumente)
            for item in antwort.get("Items", []):
                # Merkposten des quellenuebergreifenden Abgleichs teilen
                # sich die Tabelle mit den Anzeigen, sind aber keine.
                if fingerabdruck.ist_merkposten(item.get("referenznummer")):
                    continue
                yield Eintrag.aus_item(item)

            # Scan liefert bei groesseren Tabellen nur eine Teilmenge und
            # den Schluessel, ab dem es weitergeht.
            if "LastEvaluatedKey" not in antwort:
                return
            argumente["ExclusiveStartKey"] = antwort["LastEvaluatedKey"]

    def setze_status(self, referenznummer: str, neuer_status: str) -> Eintrag:
        geprueft = st.pruefe(neuer_status)

        ausdruck = "SET #s = :s, geaendert_am = :jetzt"
        werte: dict[str, Any] = {":s": geprueft, ":jetzt": int(time.time())}

        if st.ist_verfolgt(geprueft):
            # Sobald eine Bewerbung laeuft, darf die Aufbewahrungsfrist
            # den Eintrag nicht mehr loeschen.
            ausdruck += " REMOVE ablauf_zeitpunkt"

        try:
            antwort = self._tabelle.update_item(
                Key={"referenznummer": referenznummer},
                UpdateExpression=ausdruck,
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues=werte,
                # Nur bestehende Anzeigen aendern - ein Tippfehler in der
                # Referenznummer soll keinen leeren Eintrag anlegen.
                ConditionExpression="attribute_exists(referenznummer)",
                ReturnValues="ALL_NEW",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise UnbekannteAnzeige(referenznummer) from exc
            raise

        return Eintrag.aus_item(antwort["Attributes"])
