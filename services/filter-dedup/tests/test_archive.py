"""Test des Ablageschemas."""
import re

from filter_dedup.archive import Archiv


def test_schluessel_ist_nach_datum_partitioniert():
    schluessel = Archiv.schluessel("10001-1003552327-S")

    assert re.fullmatch(
        r"raw/jahr=\d{4}/monat=\d{2}/tag=\d{2}/10001-1003552327-S\.json", schluessel
    )


def test_schraegstrich_erzeugt_keine_zusaetzliche_ebene():
    schluessel = Archiv.schluessel("abc/def")

    assert schluessel.endswith("/abc_def.json")
    assert schluessel.count("/") == 4
