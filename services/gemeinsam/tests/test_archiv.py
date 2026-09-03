"""Tests des Archivs und des Detailabrufs.

S3 wird durch ein Doppel ersetzt. Geprueft wird vor allem, dass Schreiber
und Leser dasselbe Ablageschema verwenden - liefen die auseinander,
faende der Export die Rohdaten nicht mehr.
"""
from datetime import datetime, timezone

import pytest

from gemeinsam import archiv as ar
from gemeinsam import jobdetail

ERFASST = int(datetime(2025, 9, 1, 12, 0, tzinfo=timezone.utc).timestamp())


class FakeS3:
    def __init__(self, objekte=None):
        self.objekte = objekte or {}
        self.gefragt = []

    def get_object(self, Bucket, Key):
        from botocore.exceptions import ClientError

        self.gefragt.append(Key)
        if Key not in self.objekte:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "x"}}, "GetObject")

        class Koerper:
            def __init__(self, inhalt):
                self._inhalt = inhalt

            def read(self):
                return self._inhalt

        return {"Body": Koerper(self.objekte[Key])}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objekte[Key] = Body


def test_rohschluessel_folgt_dem_pfad_des_archivs():
    """Muss zum Schreiber in filter_dedup/archive.py passen."""
    tag = datetime(2025, 9, 1, tzinfo=timezone.utc)

    assert ar.rohschluessel("10001-1-S", tag) == "raw/jahr=2025/monat=09/tag=01/10001-1-S.json"


def test_schraegstriche_erzeugen_keine_zusaetzlichen_ebenen():
    assert "/" not in ar.sicherer_name("10001/1-S")
    assert ar.detailschluessel("10001/1-S") == "detail/10001_1-S.json"


def test_rohdaten_werden_ueber_das_funddatum_gefunden():
    s3 = FakeS3({"raw/jahr=2025/monat=09/tag=01/10001-1-S.json": b'{"firma": "Beispiel"}'})

    treffer = ar.Archiv("eimer", s3).rohdaten("10001-1-S", ERFASST)

    assert treffer == {"firma": "Beispiel"}
    assert len(s3.gefragt) == 1


def test_lauf_ueber_mitternacht_findet_den_vortag():
    s3 = FakeS3({"raw/jahr=2025/monat=08/tag=31/10001-1-S.json": b'{"firma": "Beispiel"}'})

    treffer = ar.Archiv("eimer", s3).rohdaten("10001-1-S", ERFASST)

    assert treffer == {"firma": "Beispiel"}


def test_fehlende_rohdaten_sind_kein_fehler():
    archiv = ar.Archiv("eimer", FakeS3())

    assert archiv.rohdaten("10001-1-S", ERFASST) is None
    assert archiv.detail("10001-1-S") is None


def test_ohne_funddatum_wird_nicht_gesucht():
    s3 = FakeS3()

    assert ar.Archiv("eimer", s3).rohdaten("10001-1-S", 0) is None
    assert s3.gefragt == []


# --- Detailabruf ------------------------------------------------------


def test_referenznummer_steht_base64_im_pfad():
    url = jobdetail.baue_url("10001-1003552327-S")

    assert url.endswith("/pc/v4/jobdetails/MTAwMDEtMTAwMzU1MjMyNy1T")


def test_vierhundertvier_bedeutet_zurueckgezogen():
    import urllib.error

    def oeffner(anfrage, timeout):
        raise urllib.error.HTTPError(anfrage.full_url, 404, "weg", {}, None)

    assert jobdetail.hole("10001-1-S", oeffner) is None


def test_andere_fehler_werden_gemeldet():
    import urllib.error

    def oeffner(anfrage, timeout):
        raise urllib.error.HTTPError(anfrage.full_url, 500, "kaputt", {}, None)

    with pytest.raises(jobdetail.JobdetailError):
        jobdetail.hole("10001-1-S", oeffner)


# --- Bestand durchgehen -----------------------------------------------


class FakeSeiten:
    """S3-Doppel mit Auflistung, wie sie die Trendauswertung braucht."""

    def __init__(self, objekte):
        self.objekte = objekte
        self.gelesen = []

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        objekte = self.objekte

        class Paginator:
            def paginate(self, Bucket, Prefix):
                passend = sorted(k for k in objekte if k.startswith(Prefix))
                # In zwei Seiten, damit auch das Blaettern geprueft ist.
                yield {"Contents": [{"Key": k} for k in passend[:2]]}
                yield {"Contents": [{"Key": k} for k in passend[2:]]}

        return Paginator()

    def get_object(self, Bucket, Key):
        self.gelesen.append(Key)

        class Koerper:
            def __init__(self, inhalt):
                self._inhalt = inhalt

            def read(self):
                return self._inhalt

        return {"Body": Koerper(self.objekte[Key])}


def test_dieselbe_anzeige_wird_nur_einmal_gezaehlt():
    """Das Suchfenster von sieben Tagen archiviert sie mehrfach."""
    s3 = FakeSeiten({
        "raw/jahr=2026/monat=08/tag=30/10001-1-S.json": b'{"a": 1}',
        "raw/jahr=2026/monat=08/tag=31/10001-1-S.json": b'{"a": 1}',
        "raw/jahr=2026/monat=09/tag=01/10001-1-S.json": b'{"a": 1}',
        "raw/jahr=2026/monat=09/tag=01/10001-2-S.json": b'{"a": 2}',
    })

    ergebnis = list(ar.Archiv("eimer", s3).alle_anzeigen())

    assert [inhalt for _, inhalt in ergebnis] == [{"a": 1}, {"a": 2}]
    # Nur die Erstvorkommen werden ueberhaupt geladen.
    assert len(s3.gelesen) == 2


def test_erstes_vorkommen_bestimmt_das_datum():
    s3 = FakeSeiten({
        "raw/jahr=2026/monat=08/tag=30/10001-1-S.json": b'{"a": 1}',
        "raw/jahr=2026/monat=09/tag=01/10001-1-S.json": b'{"a": 1}',
    })

    (tag, _), = list(ar.Archiv("eimer", s3).alle_anzeigen())

    assert tag == datetime(2026, 8, 30).date()


def test_zeitraum_grenzt_ohne_zu_lesen_ein():
    s3 = FakeSeiten({
        "raw/jahr=2026/monat=07/tag=01/10001-1-S.json": b'{"a": 1}',
        "raw/jahr=2026/monat=09/tag=01/10001-2-S.json": b'{"a": 2}',
    })

    ergebnis = list(
        ar.Archiv("eimer", s3).alle_anzeigen(seit=datetime(2026, 8, 1).date())
    )

    assert [inhalt for _, inhalt in ergebnis] == [{"a": 2}]
    assert s3.gelesen == ["raw/jahr=2026/monat=09/tag=01/10001-2-S.json"]
