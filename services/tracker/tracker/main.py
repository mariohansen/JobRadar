"""Bewerbungs-Tracker.

Aufrufbeispiele:
    python -m tracker.main liste
    python -m tracker.main liste --status BEWORBEN
    python -m tracker.main zeige 10001-1003552327-S
    python -m tracker.main setze 10001-1003552327-S BEWORBEN
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from . import status as st
from .store import Eintrag, Store, UnbekannteAnzeige


def _tabellenname() -> str:
    name = os.environ.get("DYNAMODB_TABLE_SEEN_JOBS", "").strip()
    if not name:
        raise SystemExit(
            "DYNAMODB_TABLE_SEEN_JOBS ist nicht gesetzt. Wert liefert:\n"
            "  terraform -chdir=infra output -raw dedup_table_name"
        )
    return name


def _datum(zeitstempel: int | None) -> str:
    if not zeitstempel:
        return "-"
    return datetime.fromtimestamp(zeitstempel, tz=timezone.utc).strftime("%Y-%m-%d")


def _zeile(eintrag: Eintrag) -> str:
    titel = eintrag.titel if len(eintrag.titel) <= 52 else eintrag.titel[:49] + "..."
    return (
        f"{eintrag.status:<10} {_datum(eintrag.erfasst_am):<11} "
        f"{titel:<52} {eintrag.referenznummer}"
    )


def befehl_liste(store: Store, args: argparse.Namespace) -> int:
    nur_status = st.pruefe(args.status) if args.status else None
    eintraege = list(store.liste(nur_status))

    if not eintraege:
        print("Keine Eintraege." if not nur_status else f"Keine Eintraege mit Status {nur_status}.")
        return 0

    # Nach Bewerbungsfortschritt sortieren, innerhalb dessen neueste
    # zuerst - die interessieren beim Nachsehen am meisten.
    eintraege.sort(key=lambda e: (st.ALLE.index(e.status) if e.status in st.ALLE else 99,
                                  -e.erfasst_am))

    print(f"{'STATUS':<10} {'GEFUNDEN':<11} {'TITEL':<52} REFERENZ")
    for eintrag in eintraege:
        print(_zeile(eintrag))

    verteilung = {s: sum(1 for e in eintraege if e.status == s) for s in st.ALLE}
    zusammenfassung = "  ".join(f"{s}: {n}" for s, n in verteilung.items() if n)
    wort = "Anzeige" if len(eintraege) == 1 else "Anzeigen"
    print(f"\n{len(eintraege)} {wort} | {zusammenfassung}")
    return 0


def befehl_zeige(store: Store, args: argparse.Namespace) -> int:
    try:
        eintrag = store.hole(args.referenznummer)
    except UnbekannteAnzeige:
        print(f"Keine Anzeige mit der Referenz {args.referenznummer}.")
        return 1

    print(f"Titel:      {eintrag.titel or '-'}")
    print(f"Referenz:   {eintrag.referenznummer}")
    print(f"Status:     {eintrag.status}")
    print(f"Gefunden:   {_datum(eintrag.erfasst_am)}")
    print(f"Geaendert:  {_datum(eintrag.geaendert_am)}")
    print(f"Anzeige:    https://www.arbeitsagentur.de/jobsuche/jobdetail/{eintrag.referenznummer}")
    return 0


def befehl_setze(store: Store, args: argparse.Namespace) -> int:
    try:
        eintrag = store.setze_status(args.referenznummer, args.status)
    except st.UnbekannterStatus as exc:
        print(exc)
        return 1
    except UnbekannteAnzeige:
        print(f"Keine Anzeige mit der Referenz {args.referenznummer}.")
        return 1

    print(f"{eintrag.referenznummer} steht jetzt auf {eintrag.status}.")
    if st.ist_verfolgt(eintrag.status):
        print("Die Aufbewahrungsfrist wurde aufgehoben, der Eintrag bleibt erhalten.")
    return 0


def baue_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bewerbungsstatus verwalten.")
    unterbefehle = parser.add_subparsers(dest="befehl", required=True)

    p_liste = unterbefehle.add_parser("liste", help="Anzeigen auflisten")
    p_liste.add_argument("--status", help=f"nur diesen Status ({', '.join(st.ALLE)})")
    p_liste.set_defaults(funktion=befehl_liste)

    p_zeige = unterbefehle.add_parser("zeige", help="eine Anzeige im Detail")
    p_zeige.add_argument("referenznummer")
    p_zeige.set_defaults(funktion=befehl_zeige)

    p_setze = unterbefehle.add_parser("setze", help="Status aendern")
    p_setze.add_argument("referenznummer")
    p_setze.add_argument("status", help=", ".join(st.ALLE))
    p_setze.set_defaults(funktion=befehl_setze)

    return parser


def main(argv: list[str] | None = None) -> int:
    # Stellentitel enthalten regelmaessig Gedankenstriche und Umlaute.
    # Die Windows-Konsole verwendet standardmaessig cp1252 und ersetzt
    # alles Uebrige durch Fragezeichen.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = baue_parser().parse_args(argv)
    store = Store(_tabellenname())
    return args.funktion(store, args)


if __name__ == "__main__":
    sys.exit(main())
