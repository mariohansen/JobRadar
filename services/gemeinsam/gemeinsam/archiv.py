"""Das Rohdatenarchiv in S3, schreibend und lesend.

Geschrieben wird es vom filter-dedup auf der Instanz, gelesen vom
tracker auf dem eigenen Rechner. Beide muessen sich ueber den Ablagepfad
einig sein - deshalb steht er hier an einer Stelle statt in zwei
Diensten, die auseinanderlaufen koennen.

Zwei Ablagen mit verschiedenem Zweck:

* `raw/` haelt jede Anzeige unveraendert, so wie die API sie geliefert
  hat, nach Datum partitioniert. Kafka haelt Rohdaten nur begrenzt vor;
  das Archiv ist die einzige Moeglichkeit, eine spaetere Auswertung auf
  den vollstaendigen Bestand zu stuetzen oder einen Filterfehler
  rueckwirkend zu korrigieren.
* `detail/` haelt den Anzeigentext, den die Trefferliste nicht mitgibt
  (ADR 0001). Das ist keine Zeitreihe, sondern genau ein Stand je
  Anzeige - deshalb ohne Datumsebene und je Anzeige nur einmal geholt.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)

# Um wie viele Tage neben dem errechneten Datum zusaetzlich gesucht wird.
# Der Dedup-Schritt setzt `erfasst_am` unmittelbar nach dem Archivieren;
# nur wenn ein Lauf genau ueber Mitternacht faellt, liegen beide
# Zeitstempel auf verschiedenen Tagen.
NACHBARTAGE = (0, -1, 1)


def sicherer_name(referenznummer: str) -> str:
    """Schraegstriche wuerden zusaetzliche Ebenen im Pfad erzeugen."""
    return referenznummer.replace("/", "_")


def rohschluessel(referenznummer: str, zeitpunkt: datetime | None = None) -> str:
    """Nach Datum partitionierter Ablagepfad.

    Das Schema jahr=/monat=/tag= ist die Konvention, an der Athena und
    aehnliche Werkzeuge Partitionen erkennen. Ohne sie muesste eine
    Auswertung ueber einen einzelnen Tag den gesamten Bucket lesen.
    """
    wann = zeitpunkt or datetime.now(timezone.utc)
    return (
        f"raw/jahr={wann:%Y}/monat={wann:%m}/tag={wann:%d}/"
        f"{sicherer_name(referenznummer)}.json"
    )


def detailschluessel(referenznummer: str) -> str:
    return f"detail/{sicherer_name(referenznummer)}.json"


class Archiv:
    def __init__(self, bucket: str, s3=None) -> None:
        self._s3 = s3 if s3 is not None else boto3.client("s3")
        self._bucket = bucket

    # Rueckwaertskompatibler Name aus der Zeit, als das Schema nur im
    # filter-dedup stand.
    schluessel = staticmethod(rohschluessel)

    # --- schreiben ----------------------------------------------------

    def ablegen(self, referenznummer: str, job: dict[str, Any]) -> None:
        self._schreibe(rohschluessel(referenznummer), job)

    def merke_detail(self, referenznummer: str, inhalt: dict[str, Any]) -> None:
        self._schreibe(detailschluessel(referenznummer), inhalt)

    def lege_bericht_ab(self, name: str, inhalt: str) -> str:
        """Eine HTML-Seite im Bucket ablegen und den Schluessel nennen.

        Der Inhaltstyp muss stimmen, sonst bietet der Browser die Seite
        zum Herunterladen an, statt sie anzuzeigen.
        """
        schluessel = f"dashboards/{name}"
        self._s3.put_object(
            Bucket=self._bucket,
            Key=schluessel,
            Body=inhalt.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )
        return schluessel

    def zeitlink(self, schluessel: str, sekunden: int = 7 * 24 * 3600) -> str:
        """Befristeter Link auf ein Objekt im privaten Bucket.

        Damit ist die Seite von jedem Geraet aus erreichbar, ohne den
        Bucket oeffentlich zu machen. Der Link traegt die Berechtigung in
        sich - wer ihn hat, kommt hinein - und laeuft deshalb ab.
        Laenger als sieben Tage laesst die Signatur ohnehin nicht zu.
        """
        return self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": schluessel},
            ExpiresIn=min(sekunden, 7 * 24 * 3600),
        )

    def _schreibe(self, schluessel: str, inhalt: dict[str, Any]) -> None:
        self._s3.put_object(
            Bucket=self._bucket,
            Key=schluessel,
            Body=json.dumps(inhalt, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )

    # --- lesen --------------------------------------------------------

    def _lade(self, schluessel: str) -> dict[str, Any] | None:
        try:
            antwort = self._s3.get_object(Bucket=self._bucket, Key=schluessel)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise
        return json.loads(antwort["Body"].read())

    def rohdaten(self, referenznummer: str, erfasst_am: int) -> dict[str, Any] | None:
        """Die Anzeige so, wie die Jobsuche-API sie geliefert hat."""
        if not erfasst_am:
            return None

        tag = datetime.fromtimestamp(erfasst_am, tz=timezone.utc)
        for versatz in NACHBARTAGE:
            treffer = self._lade(rohschluessel(referenznummer, tag + timedelta(days=versatz)))
            if treffer is not None:
                return treffer

        log.info("Keine Rohdaten im Archiv fuer %s", referenznummer)
        return None

    def detail(self, referenznummer: str) -> dict[str, Any] | None:
        return self._lade(detailschluessel(referenznummer))

    def schluesselliste(self, prefix: str = "raw/"):
        """Alle Schluessel unter einem Prefix, in Ablagereihenfolge.

        S3 liefert lexikografisch sortiert; weil der Schluessel mit
        jahr=/monat=/tag= beginnt, ist das zugleich chronologisch.
        """
        seiten = self._s3.get_paginator("list_objects_v2").paginate(
            Bucket=self._bucket, Prefix=prefix
        )
        for seite in seiten:
            for objekt in seite.get("Contents", []):
                yield objekt["Key"]

    def alle_anzeigen(self, seit: date | None = None):
        """Jede Anzeige genau einmal, aelteste zuerst.

        Der Poller sucht in einem Fenster von sieben Tagen, also wird
        dieselbe Anzeige an mehreren Tagen erneut archiviert. Fuer eine
        Auswertung waere das eine Verzerrung - und fuer den Bestand ein
        Vielfaches an Abrufen.

        Deshalb wird zuerst nur die Schluesselliste gelesen und daraus
        die Referenznummer gewonnen; geladen wird anschliessend nur das
        erste Vorkommen. Bei einem halben Jahr Archiv sind das rund
        zwanzig Auflistungen statt Zehntausender Einzelabrufe.
        """
        gesehen: set[str] = set()

        for schluessel in self.schluesselliste():
            tag = _tag_aus_schluessel(schluessel)
            if seit is not None and tag < seit:
                continue

            referenz = schluessel.rsplit("/", 1)[-1].removesuffix(".json")
            if referenz in gesehen:
                continue
            gesehen.add(referenz)

            inhalt = self._lade(schluessel)
            if inhalt is not None:
                yield tag, inhalt


def _tag_aus_schluessel(schluessel: str) -> date:
    """Das Ablagedatum, ohne das Objekt zu lesen.

    Faellt der Schluessel aus dem Schema, gilt er als sehr alt - dann
    wird er gelesen statt stillschweigend uebergangen.
    """
    teile = dict(
        stueck.split("=", 1)
        for stueck in schluessel.split("/")
        if "=" in stueck
    )
    try:
        return datetime(
            int(teile["jahr"]), int(teile["monat"]), int(teile["tag"]), tzinfo=timezone.utc
        ).date()
    except (KeyError, ValueError):
        return datetime.min.date()
