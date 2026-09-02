"""Gehaltsabgleich ueber den Entgeltatlas.

Aufrufbeispiele:
    python -m salary_check.main --titel "Senior Data Engineer"
    python -m salary_check.main --kldb 43414
    python -m salary_check.main --titel "Data Engineer" --region deutschland
"""
from __future__ import annotations

import argparse
import logging
import sys

from .entgeltatlas import (
    REGION_DEUTSCHLAND,
    REGION_HAMBURG,
    EntgeltatlasError,
    entgelt,
)
from .zuordnung import kldb_aus_titel

log = logging.getLogger(__name__)

REGIONEN = {"hamburg": REGION_HAMBURG, "deutschland": REGION_DEUTSCHLAND}


def baue_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bruttomonatsentgelt fuer einen Beruf aus dem Entgeltatlas."
    )
    gruppe = parser.add_mutually_exclusive_group(required=True)
    gruppe.add_argument(
        "--titel", help="Stellenbezeichnung, wird auf einen Schluessel abgebildet"
    )
    gruppe.add_argument("--kldb", help="KldB-Schluessel mit 3 bis 5 Ziffern")
    parser.add_argument(
        "--region",
        choices=sorted(REGIONEN),
        default="hamburg",
        help="Bezugsraum der Auswertung (Vorgabe: hamburg)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = baue_parser().parse_args(argv)

    kldb = args.kldb or kldb_aus_titel(args.titel)
    if args.titel:
        print(f"{args.titel} -> KldB {kldb}")

    try:
        wert = entgelt(kldb, REGIONEN[args.region])
    except EntgeltatlasError as exc:
        log.error("%s", exc)
        return 1

    if wert is None:
        print(f"Fuer KldB {kldb} liegen in dieser Region keine Werte vor.")
        return 0

    print(f"{wert.niveau} in {wert.region}")
    print(f"  Median            {wert.median:>6} EUR brutto im Monat")
    if wert.q25 and wert.q75:
        print(f"  Mittlere Haelfte  {wert.q25:>6} bis {wert.q75} EUR")
    if wert.fallzahl:
        print(f"  Datenbasis        {wert.fallzahl:>6} Beschaeftigte")
    return 0


if __name__ == "__main__":
    sys.exit(main())
