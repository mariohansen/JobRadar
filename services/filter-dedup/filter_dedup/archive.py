"""Rohdatenarchiv in S3.

Jede Anzeige wird unveraendert abgelegt, so wie die API sie geliefert
hat. Kafka haelt Rohdaten nur begrenzt vor; das Archiv ist die einzige
Moeglichkeit, eine spaetere Auswertung auf den vollstaendigen Bestand zu
stuetzen oder einen Filterfehler rueckwirkend zu korrigieren.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import boto3

log = logging.getLogger(__name__)


class Archiv:
    def __init__(self, bucket: str) -> None:
        self._s3 = boto3.client("s3")
        self._bucket = bucket

    def ablegen(self, referenznummer: str, job: dict[str, Any]) -> None:
        self._s3.put_object(
            Bucket=self._bucket,
            Key=self.schluessel(referenznummer),
            Body=json.dumps(job, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )

    @staticmethod
    def schluessel(referenznummer: str) -> str:
        """Nach Datum partitionierter Ablagepfad.

        Das Schema jahr=/monat=/tag= ist die Konvention, an der Athena
        und aehnliche Werkzeuge Partitionen erkennen. Ohne sie muesste
        eine Auswertung ueber einen einzelnen Tag den gesamten Bucket
        lesen.
        """
        jetzt = datetime.now(timezone.utc)
        # Schraegstriche in der Referenznummer wuerden zusaetzliche
        # Ebenen im Pfad erzeugen.
        sicher = referenznummer.replace("/", "_")
        return f"raw/jahr={jetzt:%Y}/monat={jetzt:%m}/tag={jetzt:%d}/{sicher}.json"
