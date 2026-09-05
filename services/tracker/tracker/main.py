"""Bewerbungs-Tracker.

Aufrufbeispiele:
    python -m tracker.main liste
    python -m tracker.main liste --status BEWORBEN
    python -m tracker.main zeige 10001-1003552327-S
    python -m tracker.main setze 10001-1003552327-S BEWORBEN
    python -m tracker.main export --datei Bewerbungs_Tracker.xlsx
    python -m tracker.main rueckblick
    python -m tracker.main faellig --tage 21
    python -m tracker.main warum 10001-1003552327-S
    python -m tracker.main profil
    python -m tracker.main trend --hochladen
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import Counter
from datetime import datetime, timezone

from dataclasses import replace

from . import status as st
from .store import Eintrag, Store, UnbekannteAnzeige


def _umgebung(name: str, terraform_ausgabe: str) -> str:
    wert = os.environ.get(name, "").strip()
    if not wert:
        raise SystemExit(
            f"{name} ist nicht gesetzt. Wert liefert:\n"
            f"  terraform -chdir=infra output -raw {terraform_ausgabe}"
        )
    return wert


def _tabellenname() -> str:
    return _umgebung("DYNAMODB_TABLE_SEEN_JOBS", "dedup_table_name")


def _bucketname() -> str:
    return _umgebung("S3_BUCKET_RAW_ARCHIVE", "archive_bucket_name")


def _datum(zeitstempel: int | None) -> str:
    if not zeitstempel:
        return "-"
    return datetime.fromtimestamp(zeitstempel, tz=timezone.utc).strftime("%Y-%m-%d")


def _teile_aussortierte(eintraege, mit_aussortierten: bool):
    """Trennt Anzeigen, die unter den Titel-Ausschluss fallen, ab.

    Der Dedup-Schritt legt jede gesehene Anzeige an, auch die, die der
    Filter danach verwirft - sonst wuerde dieselbe unpassende Anzeige
    jeden Poller-Lauf neu geholt. Der Tracker wendet deshalb hier
    dieselbe Liste (`gemeinsam.ausschluss`, per `MATCH_AUSSCHLUSS`
    einstellbar) noch einmal an. Nur der Startzustand GEFUNDEN wird
    aussortiert - was schon beworben ist, bleibt.

    Gibt (behalten, {grund: [referenz, ...]}) zurueck.
    """
    from gemeinsam import ausschluss

    if mit_aussortierten:
        return list(eintraege), {}

    liste = ausschluss.aus_umgebung(os.environ.get("MATCH_AUSSCHLUSS"))
    behalten = []
    aussortiert: dict[str, list[str]] = {}
    for eintrag in eintraege:
        grund = ausschluss.grund(eintrag.titel, liste) if eintrag.status == st.GEFUNDEN else None
        if grund:
            aussortiert.setdefault(grund, []).append(eintrag.referenznummer)
        else:
            behalten.append(eintrag)
    return behalten, aussortiert


def _uebernimm_status(store: Store, eintraege: list, datei: str, blattname: str | None):
    """Die Auswahl aus der Tabelle nach DynamoDB zurueckschreiben.

    Die Statusspalte ist ein Auswahlfeld - dort klickt man, nicht in der
    Kommandozeile. Bevor der Export von DynamoDB in die Tabelle
    schreibt, muss also erst der umgekehrte Weg gegangen sein, sonst
    ueberschriebe der Lauf die eigene Eingabe.

    Gibt die Eintraege mit aktualisiertem Status zurueck, dazu die
    Anzahl der Aenderungen und die nicht zuordenbaren Zellinhalte.
    """
    from . import excel

    aus_tabelle = excel.lies_status(datei, blattname)
    if not aus_tabelle:
        return eintraege, 0, []

    aktualisiert = []
    geaendert = 0
    unbekannt: list[str] = []

    for eintrag in eintraege:
        if eintrag.referenznummer not in aus_tabelle:
            aktualisiert.append(eintrag)
            continue

        gewaehlt = st.aus_tabelle(aus_tabelle[eintrag.referenznummer])
        if gewaehlt is None:
            unbekannt.append(str(aus_tabelle[eintrag.referenznummer]).strip())
            aktualisiert.append(eintrag)
            continue

        if gewaehlt == eintrag.status:
            aktualisiert.append(eintrag)
            continue

        store.setze_status(eintrag.referenznummer, gewaehlt)
        aktualisiert.append(replace(eintrag, status=gewaehlt))
        geaendert += 1

    return aktualisiert, geaendert, sorted(set(unbekannt))


def _teile_arbeitgeber(zeilen, eintraege, mit_aussortierten: bool):
    """Trennt Zeilen ab, deren Arbeitgeber auf der Ausschlussliste steht.

    Anders als der Titel steht der Firmenname nicht im Tabelleneintrag,
    sondern erst in den Rohdaten aus dem Archiv - also erst, nachdem die
    Zeilen gebaut sind. Deshalb hier und nicht in `_teile_aussortierte`.
    """
    from gemeinsam import ausschluss

    if mit_aussortierten:
        return zeilen, eintraege, {}

    liste = ausschluss.arbeitgeber_aus_umgebung(
        os.environ.get("MATCH_ARBEITGEBER_AUSSCHLUSS")
    )
    behalten_zeilen = []
    behalten_eintraege = []
    aussortiert: dict[str, list[str]] = {}

    for zeile, eintrag in zip(zeilen, eintraege):
        grund = (
            ausschluss.arbeitgeber_grund(zeile.get("Firma"), liste)
            if eintrag.status == st.GEFUNDEN
            else None
        )
        if grund:
            aussortiert.setdefault(grund, []).append(eintrag.referenznummer)
        else:
            behalten_zeilen.append(zeile)
            behalten_eintraege.append(eintrag)

    return behalten_zeilen, behalten_eintraege, aussortiert


def _melde_aussortierte(aussortiert: dict[str, list[str]]) -> None:
    if not aussortiert:
        return
    gesamt = sum(len(refs) for refs in aussortiert.values())
    aufschluesselung = ", ".join(
        f"{grund}: {len(refs)}" for grund, refs in sorted(aussortiert.items())
    )
    print(f"Aussortiert (Titel): {gesamt} ({aufschluesselung}) - mit --mit-aussortierten zeigen")


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

    eintraege, aussortiert = _teile_aussortierte(eintraege, args.mit_aussortierten)

    if not eintraege:
        print("Alle Eintraege sind aussortiert.")
        _melde_aussortierte(aussortiert)
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
    _melde_aussortierte(aussortiert)
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


def befehl_profil(store: Store | None, args: argparse.Namespace) -> int:
    from dataclasses import replace
    from pathlib import Path

    from gemeinsam import faehigkeiten as fk
    from gemeinsam import profil as pr

    ziel = Path(args.datei) if args.datei else pr.vorgabe_pfad()

    if args.anzeigen:
        try:
            eigenes = pr.lade(ziel)
        except pr.ProfilFehler as exc:
            print(exc)
            return 1
    else:
        try:
            quelle = Path(args.unterlagen) if args.unterlagen else pr.VORGABE_UNTERLAGEN
            eigenes, stumm = pr.erstelle(quelle)
        except pr.ProfilFehler as exc:
            print(exc)
            return 1

        # Eine bestehende Datei kann von Hand nachgepflegt sein. Das neu
        # Gelesene ersetzt die erkannten Begriffe, nicht die Pflege.
        if ziel.exists():
            bisher = pr.lade(ziel)
            eigenes = replace(
                eigenes, eigene=bisher.eigene, ausgeschlossen=bisher.ausgeschlossen
            )

        pr.speichere(eigenes, ziel)
        print(f"Gelesen: {', '.join(eigenes.quellen)}")
        for name in stumm:
            print(f"Ohne Textebene, vermutlich ein Scan: {name}")
        print(f"Geschrieben: {ziel}\n")

    schwerpunkte = eigenes.kern
    for kategorie, namen in fk.nach_kategorie(sorted(eigenes.alle)).items():
        # Schwerpunkte mit Stern, damit die Gewichtung sichtbar ist.
        gezeigt = [f"{n}*" if n in schwerpunkte else n for n in namen]
        print(f"{kategorie:<22} {', '.join(gezeigt)}")

    print(f"\n{len(eigenes.alle)} Fähigkeiten, davon {len(schwerpunkte)} Schwerpunkte (*)")
    if not args.anzeigen:
        print(f"Nachbessern: 'eigene' und 'ausgeschlossen' in {ziel}")
    return 0


def _lade_profil(args: argparse.Namespace):
    """Faehigkeitsprofil, oder None.

    Ein fehlendes Profil ist kein Fehler: der Export laesst dann die
    Passungsspalten weg, der Trend zeigt nur die Marktzahlen.
    """
    from pathlib import Path

    from gemeinsam import profil as pr

    if args.ohne_passung:
        return None

    pfad = Path(args.profil) if args.profil else pr.vorgabe_pfad()
    if not pfad.exists():
        print(f"Kein Profil unter {pfad} - weiter ohne Abgleich.")
        print("Anlegen mit: python -m tracker.main profil")
        return None

    return pr.lade(pfad)


def befehl_trend(store: Store | None, args: argparse.Namespace) -> int:
    from datetime import date, timedelta
    from pathlib import Path

    from gemeinsam.archiv import Archiv
    from gemeinsam import profil as pr

    from . import bericht, trend

    archiv = Archiv(_bucketname())
    eigenes_profil = _lade_profil(args)
    seit = date.today() - timedelta(days=args.tage) if args.tage else None

    def fortschritt(laufend: int) -> None:
        print(f"\r{laufend} Anzeigen gelesen", end="", flush=True)

    auswertung = trend.werte_aus(
        archiv.alle_anzeigen(seit),
        eigenes_profil,
        # Ohne die Anzeigentexte bleibt nur der Titel - dann zaehlt der
        # Bericht vor allem Berufsbezeichnungen.
        detail_zu=None if args.ohne_texte else archiv.detail,
        fortschritt=fortschritt,
    )
    print()

    if not auswertung.anzeigen:
        print("Keine Anzeigen im Archiv fuer diesen Zeitraum.")
        return 0

    ziel = Path(args.datei) if args.datei else pr.wurzel() / "dashboards" / "skill-trend.html"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(bericht.baue(auswertung, eigenes_profil), encoding="utf-8")

    print(f"{auswertung.anzeigen} Anzeigen ausgewertet, {ziel}")

    if eigenes_profil is not None:
        print("\nWas dir am häufigsten fehlt:")
        for begriff, anzahl, anteil in auswertung.wichtigste_luecken(8):
            print(f"  {anteil:>4.0%}  {anzahl:>4}x  {begriff}")

    # Der blinde Fleck des Verzeichnisses: was oft verlangt wird, aber
    # gar nicht darin steht, taucht in den Luecken oben nie auf.
    fehlend = [
        eintrag for eintrag in auswertung.fehlende_begriffe(12) if eintrag[1] >= 3
    ]
    if fehlend:
        print("\nBegriffe, die das Verzeichnis noch nicht kennt:")
        for begriff, anzahl, anteil in fehlend:
            print(f"  {anteil:>4.0%}  {anzahl:>4}x  {begriff}")
        print("  Was davon zaehlt, gehoert nach gemeinsam/faehigkeiten.py.")

    if args.hochladen:
        schluessel = archiv.lege_bericht_ab("skill-trend.html", ziel.read_text(encoding="utf-8"))
        print(f"\nAbrufbar (7 Tage gültig, der Link ist der Schlüssel):\n{archiv.zeitlink(schluessel)}")

    return 0


def befehl_export(store: Store, args: argparse.Namespace) -> int:
    # openpyxl wird nur hier gebraucht. Ein fehlendes Paket soll die
    # uebrigen Befehle nicht unbenutzbar machen.
    from gemeinsam.archiv import Archiv

    from . import excel, export as ex, felder

    nur_status = st.pruefe(args.status) if args.status else None
    # Aeltester Fund zuerst - der Rang ergibt sich spaeter aus der
    # Passung, aber eine stabile Grundordnung erleichtert das Lesen.
    eintraege = sorted(store.liste(nur_status), key=lambda e: e.erfasst_am)
    if not eintraege:
        print("Keine Eintraege zum Exportieren.")
        return 0

    # Zuerst die Gegenrichtung: was in der Tabelle ausgewaehlt wurde,
    # gehoert nach DynamoDB, bevor von dort zurueckgeschrieben wird.
    eintraege, uebernommen, unbekannt = _uebernimm_status(
        store, eintraege, args.datei, args.blatt
    )
    if uebernommen:
        print(f"Aus der Tabelle uebernommen: {uebernommen} Statusaenderung(en)")
    for wert in unbekannt:
        print(f"Unbekannter Status in der Tabelle, uebergangen: {wert!r}")

    # "Nicht interessant" heisst: nicht mehr anzeigen. Der Eintrag bleibt
    # in DynamoDB, damit dieselbe Anzeige nicht beim naechsten Lauf
    # wieder auftaucht.
    uninteressant = {
        e.referenznummer for e in eintraege if e.status == st.UNINTERESSANT
    }
    eintraege = [e for e in eintraege if e.status != st.UNINTERESSANT]

    eintraege, aussortiert = _teile_aussortierte(eintraege, args.mit_aussortierten)
    aussortierte_referenzen = {r for refs in aussortiert.values() for r in refs}

    quellen = ex.Quellen(
        Archiv(_bucketname()),
        mit_details=not args.ohne_details,
        details_erneuern=args.details_erneuern,
    )
    eigenes_profil = _lade_profil(args)

    def fortschritt(laufend: int, gesamt: int) -> None:
        print(f"\r{laufend}/{gesamt} Anzeigen gelesen", end="", flush=True)

    zeilen = ex.baue_zeilen(eintraege, quellen, fortschritt, eigenes_profil)
    print()

    # Der Arbeitgeber steht erst jetzt fest - er kommt aus dem Archiv,
    # nicht aus dem Tabelleneintrag.
    zeilen, eintraege, wegen_firma = _teile_arbeitgeber(
        zeilen, eintraege, args.mit_aussortierten
    )
    for grund, refs in wegen_firma.items():
        aussortiert.setdefault(grund, []).extend(refs)
        aussortierte_referenzen.update(refs)

    spalten = felder.SPALTEN_MIT_PASSUNG if eigenes_profil else felder.SPALTEN_STANDARD
    bericht = excel.schreibe(
        args.datei,
        zeilen,
        args.blatt,
        args.ueberschreiben,
        spalten,
        entfernen=aussortierte_referenzen,
        nicht_interessant=uninteressant,
    )

    print(f"{bericht.datei}: {bericht.neu} neu, {bericht.aktualisiert} aktualisiert")
    if bericht.entfernt:
        print(f"Aus der Tabelle entfernt: {bericht.entfernt}")
    if bericht.sicherung:
        print(f"Sicherung der vorherigen Fassung: {bericht.sicherung}")

    if eigenes_profil:
        verteilung = Counter(z.get("Passung", "") for z in zeilen)
        print(
            "Passung: "
            + "  ".join(f"{stufe}: {n}" for stufe, n in sorted(verteilung.items()) if stufe)
        )

    print("Status in der Tabelle waehlen: " + ", ".join(st.AUSWAHL))
    _melde_aussortierte(aussortiert)
    return 0


# Punktebaender fuer den Rueckblick. Die Grenzen liegen auf den
# Passungsschwellen, damit sich ablesen laesst, ob A wirklich besser
# laeuft als B - das ist der Zweck der Uebung.
BAENDER = ((70, 100), (55, 69), (35, 54), (0, 34))


def _bewerte_bestand(store: Store, args: argparse.Namespace, nur_entschieden: bool):
    """Alle Eintraege mit ihrer heutigen Punktzahl.

    Neu gerechnet statt gespeichert: aendert sich die Formel oder waechst
    das Profil, soll der Rueckblick die neue Bewertung beurteilen und
    nicht die von damals.
    """
    from gemeinsam import anzeige, passung
    from gemeinsam.archiv import Archiv

    from . import export as ex

    eigenes_profil = _lade_profil(args)
    if eigenes_profil is None:
        return None, []

    eintraege = [
        e for e in store.liste()
        if not nur_entschieden or e.status != st.GEFUNDEN
    ]
    if not eintraege:
        return eigenes_profil, []

    quellen = ex.Quellen(Archiv(_bucketname()), mit_details=not args.ohne_details)
    bewertet = []
    for laufend, eintrag in enumerate(eintraege, start=1):
        print(f"\r{laufend}/{len(eintraege)} Anzeigen bewertet", end="", flush=True)
        roh = quellen.rohdaten(eintrag)
        detail = quellen.detail(eintrag, roh)
        titel = roh.get("stellenangebotsTitel") or eintrag.titel
        bewertung = passung.bewerte(eigenes_profil, titel, anzeige.text(roh, detail))
        bewertet.append((eintrag, bewertung))
    print()
    return eigenes_profil, bewertet


def befehl_rueckblick(store: Store, args: argparse.Namespace) -> int:
    """Was aus den Bewerbungen wurde, nach Punktzahl aufgeschluesselt.

    Die Schwellen der Passung sind gesetzt und nicht gemessen. Hier
    stehen sie zum ersten Mal gegen die Wirklichkeit: fuehren hohe
    Punktzahlen wirklich haeufiger zu einem Gespraech?
    """
    eigenes_profil, bewertet = _bewerte_bestand(store, args, nur_entschieden=True)
    if eigenes_profil is None:
        print("Ohne Faehigkeitsprofil gibt es keine Punktzahl zum Abgleichen.")
        print("Anlegen mit: python -m tracker.main profil")
        return 1
    if not bewertet:
        print("Noch nichts entschieden - der Rueckblick braucht bewertete Bewerbungen.")
        return 0

    beworben = [
        (e, b) for e, b in bewertet
        if e.status in st.LAEUFT or e.status == st.ABSAGE
    ]
    verworfen = [(e, b) for e, b in bewertet if e.status == st.UNINTERESSANT]

    kopf = (
        f"{'Punkte':<9}{'beworben':>9}{'Interview':>11}{'Zusage':>8}"
        f"{'Absage':>8}{'offen':>7}{'Quote':>8}"
    )
    print(kopf)
    for von, bis in BAENDER:
        im_band = [(e, b) for e, b in beworben if von <= b.punkte <= bis]
        if not im_band:
            continue
        interview = sum(1 for e, _ in im_band if e.status == st.INTERVIEW)
        zusage = sum(1 for e, _ in im_band if e.status == st.ZUSAGE)
        absage = sum(1 for e, _ in im_band if e.status == st.ABSAGE)
        offen = sum(1 for e, _ in im_band if e.status == st.BEWORBEN)
        # Eine Quote hat nur Sinn ueber die schon beantworteten.
        beantwortet = interview + zusage + absage
        quote = f"{(interview + zusage) / beantwortet:.0%}" if beantwortet else "-"
        band = f"{von}-{bis}"
        print(
            f"{band:<9}{len(im_band):>9}{interview:>11}{zusage:>8}"
            f"{absage:>8}{offen:>7}{quote:>8}"
        )

    if not beworben:
        print("  (noch keine Bewerbung abgeschickt)")

    if verworfen:
        schnitt = sum(b.punkte for _, b in verworfen) / len(verworfen)
        print(
            f"\nAls 'Nicht interessant' verworfen: {len(verworfen)}, "
            f"im Schnitt {schnitt:.0f} Punkte"
        )
        if beworben:
            schnitt_beworben = sum(b.punkte for _, b in beworben) / len(beworben)
            print(f"Abgeschickt dagegen im Schnitt {schnitt_beworben:.0f} Punkte")
            if schnitt > schnitt_beworben:
                print(
                    "Die Bewertung liegt daneben: du verwirfst die hoeher "
                    "bewerteten Anzeigen."
                )

    mit_antwort = sum(
        1 for e, _ in beworben
        if e.status in (st.INTERVIEW, st.ZUSAGE, st.ABSAGE)
    )
    if beworben:
        print(f"\n{len(beworben)} Bewerbungen, {mit_antwort} beantwortet.")
    if mit_antwort < 10:
        print("Unter zehn Rueckmeldungen ist jede Quote hier Zufall.")
    return 0


def befehl_faellig(store: Store, args: argparse.Namespace) -> int:
    """Bewerbungen, die seit laengerem ohne Rueckmeldung sind.

    Braucht keine handgepflegte Frist: wann der Status zuletzt geaendert
    wurde, steht ohnehin in DynamoDB.
    """
    jetzt = int(datetime.now(tz=timezone.utc).timestamp())
    offen = []
    for eintrag in store.liste():
        if eintrag.status not in (st.BEWORBEN, st.INTERVIEW):
            continue
        seit = eintrag.geaendert_am or eintrag.erfasst_am
        tage = (jetzt - seit) // 86400 if seit else 0
        if tage >= args.tage:
            offen.append((tage, eintrag))

    if not offen:
        print(f"Nichts offen seit mehr als {args.tage} Tagen.")
        return 0

    offen.sort(key=lambda paar: -paar[0])
    print(f"{'TAGE':<6}{'STATUS':<13}{'TITEL':<52}REFERENZ")
    for tage, eintrag in offen:
        titel = eintrag.titel if len(eintrag.titel) <= 50 else eintrag.titel[:47] + "..."
        print(f"{tage:<6}{st.text(eintrag.status):<13}{titel:<52}{eintrag.referenznummer}")
    print(f"\n{len(offen)} ohne Rueckmeldung seit mindestens {args.tage} Tagen.")
    return 0


def befehl_warum(store: Store, args: argparse.Namespace) -> int:
    """Warum ist diese Anzeige (nicht) in der Tabelle gelandet?

    Geht dieselben Stufen durch wie die Pipeline und sagt bei jeder, was
    sie entschieden haette. Erspart die Fehlersuche ueber journalctl auf
    der Instanz.
    """
    from gemeinsam import anzeige, ausschluss, fingerabdruck, passung
    from gemeinsam.archiv import Archiv

    from . import export as ex

    referenz = args.referenznummer
    print(f"Referenz:      {referenz}\n")

    try:
        eintrag = store.hole(referenz)
    except UnbekannteAnzeige:
        print("1. Bekannt?    nein - steht nicht in DynamoDB.")
        print("   Entweder nie gefunden (Suchbegriff, Ort, Zeitfenster)")
        print("   oder die Aufbewahrungsfrist ist abgelaufen.")
        return 0

    print(f"1. Bekannt?    ja, erfasst am {_datum(eintrag.erfasst_am)}")
    print(f"   Status:     {st.text(eintrag.status) or 'noch nichts entschieden'}")

    quellen = ex.Quellen(Archiv(_bucketname()), mit_details=not args.ohne_details)
    roh = quellen.rohdaten(eintrag)
    detail = quellen.detail(eintrag, roh)
    titel = roh.get("stellenangebotsTitel") or eintrag.titel
    print(f"   Titel:      {titel}")
    print(f"   Quelle:     {roh.get('quelle') or 'arbeitsagentur (oder Archiv fehlt)'}")

    abdruck = fingerabdruck.schluessel(roh) if roh else None
    if abdruck is None:
        print("\n2. Doppelt?    nicht pruefbar - Arbeitgeber oder Titel fehlen.")
    else:
        try:
            merkposten = store.hole(abdruck)
        except UnbekannteAnzeige:
            print(f"\n2. Doppelt?    nein, Fingerabdruck {abdruck} ist frei.")
        else:
            print(f"\n2. Doppelt?    Fingerabdruck {abdruck} ist vergeben.")
            zuerst = merkposten.titel or "(nicht vermerkt)"
            print(f"   zuerst als:  {zuerst}")

    liste = ausschluss.aus_umgebung(os.environ.get("MATCH_AUSSCHLUSS"))
    grund = ausschluss.grund(titel, liste)
    if grund:
        print(f"\n3. Ausschluss? ja - der Titel enthaelt {grund!r}.")
        print("   Mit --mit-aussortierten kommt sie trotzdem in die Tabelle.")
    else:
        print("\n3. Ausschluss? nein.")

    eigenes_profil = _lade_profil(args)
    if eigenes_profil is None:
        print("\n4. Passung:    kein Profil geladen.")
        return 0

    bewertung = passung.bewerte(eigenes_profil, titel, anzeige.text(roh, detail))
    punkte = f" ({bewertung.punkte} Punkte)" if bewertung.brauchbar else ""
    print(f"\n4. Passung:    {bewertung.stufe}{punkte}")
    if bewertung.treffer:
        print(f"   passt:      {bewertung.treffertext}")
    if bewertung.luecken:
        print(f"   fehlt:      {bewertung.lueckentext}")
    if not anzeige.beschreibung(detail, roh):
        print("   Kein Anzeigentext vorhanden - daher 'zu wenig Angaben'.")
    return 0


def baue_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bewerbungsstatus verwalten.")
    unterbefehle = parser.add_subparsers(dest="befehl", required=True)

    p_liste = unterbefehle.add_parser("liste", help="Anzeigen auflisten")
    p_liste.add_argument("--status", help=f"nur diesen Status ({', '.join(st.ALLE)})")
    p_liste.add_argument(
        "--mit-aussortierten",
        action="store_true",
        help="auch Anzeigen zeigen, deren Titel unter den Ausschluss fällt "
        "(senior, lead, praktikum …)",
    )
    p_liste.set_defaults(funktion=befehl_liste)

    p_zeige = unterbefehle.add_parser("zeige", help="eine Anzeige im Detail")
    p_zeige.add_argument("referenznummer")
    p_zeige.set_defaults(funktion=befehl_zeige)

    p_setze = unterbefehle.add_parser("setze", help="Status aendern")
    p_setze.add_argument("referenznummer")
    p_setze.add_argument("status", help=", ".join(st.ALLE))
    p_setze.set_defaults(funktion=befehl_setze)

    p_export = unterbefehle.add_parser(
        "export", help="Anzeigen in eine Excel-Tabelle schreiben"
    )
    p_export.add_argument(
        "--datei", required=True, help="Zieldatei (.xlsx). Wird ergaenzt, nicht ersetzt"
    )
    p_export.add_argument("--blatt", help="Arbeitsblatt (Vorgabe: das erste)")
    p_export.add_argument("--status", help=f"nur diesen Status ({', '.join(st.ALLE)})")
    p_export.add_argument(
        "--ohne-details",
        action="store_true",
        help="ohne Abruf der Anzeigentexte - schneller, laesst aber Kontakt, "
        "Benefits und Gehalt leer und die Passung bei 'zu wenig Angaben'",
    )
    p_export.add_argument(
        "--details-erneuern",
        action="store_true",
        help="zwischengespeicherte Anzeigentexte neu abrufen",
    )
    p_export.add_argument(
        "--profil",
        default=None,
        help="Faehigkeitsprofil fuer die Passungsbewertung "
        "(Vorgabe: bewerbung/profil.json im Projektordner)",
    )
    p_export.add_argument(
        "--ohne-passung",
        action="store_true",
        help="ohne Passungsbewertung, auch wenn ein Profil vorliegt",
    )
    p_export.add_argument(
        "--ueberschreiben",
        action="store_true",
        help="auch vorbelegte Spalten neu schreiben, die schon gefuellt sind",
    )
    p_export.add_argument(
        "--mit-aussortierten",
        action="store_true",
        help="Anzeigen behalten, deren Titel unter den Ausschluss fällt "
        "(senior, lead, praktikum …); sonst kommen sie nicht in die Tabelle "
        "und bereits vorhandene GEFUNDEN-Zeilen werden entfernt",
    )
    p_export.set_defaults(funktion=befehl_export)

    p_rueckblick = unterbefehle.add_parser(
        "rueckblick", help="was aus den Bewerbungen wurde, nach Punktzahl"
    )
    p_rueckblick.add_argument("--profil", default=None, help="Faehigkeitsprofil")
    p_rueckblick.add_argument(
        "--ohne-details", action="store_true", help="ohne Anzeigentexte - grober"
    )
    p_rueckblick.add_argument("--ohne-passung", action="store_true", help=argparse.SUPPRESS)
    p_rueckblick.set_defaults(funktion=befehl_rueckblick)

    p_faellig = unterbefehle.add_parser(
        "faellig", help="Bewerbungen ohne Rueckmeldung"
    )
    p_faellig.add_argument(
        "--tage", type=int, default=14, help="ab wie vielen Tagen (Vorgabe: 14)"
    )
    p_faellig.set_defaults(funktion=befehl_faellig)

    p_warum = unterbefehle.add_parser(
        "warum", help="warum eine Anzeige (nicht) in der Tabelle steht"
    )
    p_warum.add_argument("referenznummer")
    p_warum.add_argument("--profil", default=None, help="Faehigkeitsprofil")
    p_warum.add_argument(
        "--ohne-details", action="store_true", help="ohne Anzeigentext nachladen"
    )
    p_warum.add_argument("--ohne-passung", action="store_true", help=argparse.SUPPRESS)
    p_warum.set_defaults(funktion=befehl_warum)

    p_profil = unterbefehle.add_parser(
        "profil", help="Faehigkeitsprofil aus den eigenen Unterlagen"
    )
    p_profil.add_argument(
        "--unterlagen",
        default=None,
        help="Verzeichnis mit Lebenslauf und Zeugnissen "
        "(Vorgabe: bewerbung/ im Projektordner)",
    )
    p_profil.add_argument(
        "--datei", default=None, help="Ablage des Profils (Vorgabe: bewerbung/profil.json)"
    )
    p_profil.add_argument(
        "--anzeigen",
        action="store_true",
        help="nur das vorhandene Profil ausgeben, ohne es neu zu lesen",
    )
    # Das Profil entsteht ausschliesslich aus lokalen Dateien - dafuer
    # braucht es weder Tabelle noch AWS-Zugangsdaten.
    p_profil.set_defaults(funktion=befehl_profil, braucht_store=False)

    p_trend = unterbefehle.add_parser(
        "trend", help="auswerten, was der Markt verlangt und was davon fehlt"
    )
    p_trend.add_argument(
        "--tage", type=int, default=0, help="nur die letzten N Tage (Vorgabe: alles)"
    )
    p_trend.add_argument(
        "--datei", default=None, help="Zieldatei (Vorgabe: dashboards/skill-trend.html)"
    )
    p_trend.add_argument(
        "--ohne-texte",
        action="store_true",
        help="ohne die zwischengespeicherten Anzeigentexte - schneller, aber grober",
    )
    p_trend.add_argument(
        "--hochladen",
        action="store_true",
        help="zusaetzlich nach S3 legen und einen befristeten Link ausgeben",
    )
    p_trend.add_argument("--profil", default=None, help="Faehigkeitsprofil")
    p_trend.add_argument(
        "--ohne-passung", action="store_true", help="nur Marktzahlen, kein Abgleich"
    )
    # Liest das Archiv, nicht die Tabelle.
    p_trend.set_defaults(funktion=befehl_trend, braucht_store=False)

    return parser


def main(argv: list[str] | None = None) -> int:
    # Stellentitel enthalten regelmaessig Gedankenstriche und Umlaute.
    # Die Windows-Konsole verwendet standardmaessig cp1252 und ersetzt
    # alles Uebrige durch Fragezeichen.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # Der Export meldet einzelne unerreichbare Anzeigen als Warnung und
    # macht weiter. Ohne diese Zeile bliebe das unsichtbar.
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    args = baue_parser().parse_args(argv)
    store = Store(_tabellenname()) if getattr(args, "braucht_store", True) else None
    return args.funktion(store, args)


if __name__ == "__main__":
    sys.exit(main())
