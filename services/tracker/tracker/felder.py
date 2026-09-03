"""Abbildung einer Anzeige auf die Spalten des Bewerbungs-Trackers.

Drei Quellen fliessen zusammen:

* der Tabelleneintrag aus DynamoDB - Referenz, Titel, Status, Funddatum,
* die archivierten Rohdaten aus S3 - Firma, Ort, Homeoffice-Anteil,
* die Detailansicht der Jobsuche - Anzeigentext, Kontakt, Verguetung.

Fehlt eine Quelle, bleiben die betroffenen Zellen leer, statt dass der
Export abbricht. Das ist der Normalfall und kein Fehler: das Archiv
reicht nur so weit zurueck wie die Anzeige selbst, und zurueckgezogene
Anzeigen liefern kein Detail mehr.

Alles hier ist Feldzuordnung und Mustersuche - kein Sprachmodell, keine
Kosten je Anzeige. Was sich nicht eindeutig ableiten laesst, bleibt
Handarbeit.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

from gemeinsam import anzeige, entfernung, homeoffice as ho

from . import benefits
from . import status as st

# Die Reihenfolge der Tabelle. Zugeordnet wird ueber die Ueberschrift,
# nicht ueber die Position - eine umsortierte Tabelle bleibt lesbar.
#
# Die Passungsspalten kommen nur mit Faehigkeitsprofil dazu, stehen dann
# aber weit vorn: die Tabelle wird beim Export nach ihnen sortiert, und
# was den Rang bestimmt, gehoert in Sichtweite.
SPALTEN_STANDARD: tuple[str, ...] = (
    "Nr.",
    "Status",
    "Firma",
    "Position",
    "Link zur Ausschreibung",
    "Standort",
    "Entfernung (km)",
    "Benefits",
    "Homeoffice-Modell",
    "Gehalt",
    "Alter (Tage)",
    "Kontakt",
    "Quelle",
)

SPALTEN_MIT_PASSUNG: tuple[str, ...] = (
    "Nr.",
    "Passung",
    "Punkte",
    "Status",
    "Firma",
    "Position",
    "Link zur Ausschreibung",
    "Standort",
    "Entfernung (km)",
    "Benefits",
    "Homeoffice-Modell",
    "Gehalt",
    "Alter (Tage)",
    "Treffer",
    "Lücken",
    "Kontakt",
    "Quelle",
)

# Rueckwaertskompatibler Name: der Standardsatz ohne Passung.
SPALTEN: tuple[str, ...] = SPALTEN_STANDARD

# Zusaetzliche, ausgeblendete Spalte. Ohne sie liesse sich beim naechsten
# Export nicht erkennen, welche Zeile zu welcher Anzeige gehoert.
SPALTE_REFERENZ = "Referenz"

# "Treffer" und "Lücken" stehen neben der Stufe, damit sie nachpruefbar
# ist statt geglaubt werden zu muessen.
PASSUNGSSPALTEN: tuple[str, ...] = ("Passung", "Punkte", "Treffer", "Lücken")

# Stehen in den Rohdaten und kommen deshalb immer dazu. Beide als Zahl,
# damit Excel danach sortieren und filtern kann.
ZUSATZSPALTEN: tuple[str, ...] = ("Alter (Tage)", "Entfernung (km)")

# Wird bei jedem Export neu geschrieben. Diese Werte stehen fest in den
# Daten; eine Aenderung von Hand waere beim naechsten Lauf wieder weg.
AUTOMATISCH = frozenset(
    {
        "Nr.",
        "Firma",
        "Position",
        "Link zur Ausschreibung",
        "Standort",
        "Homeoffice-Modell",
        "Quelle",
        # Der Status wird in der Tabelle gepflegt, nicht hier. Er steht
        # trotzdem unter "automatisch", weil der Export die Auswahl vorher
        # nach DynamoDB zurueckliest - danach ist der gespeicherte Wert
        # der richtige.
        "Status",
        # Das Alter aendert sich jeden Tag von allein.
        *ZUSATZSPALTEN,
        # Die Bewertung haengt am Profil. Waechst das Profil, sollen die
        # Stufen nachziehen statt auf dem alten Stand einzufrieren.
        *PASSUNGSSPALTEN,
    }
)

# Wird nur eingetragen, solange die Zelle leer ist. Ein Vorschlag, den
# eine eigene Eintragung jederzeit ersetzt.
VORSCHLAG = frozenset(
    {
        "Gehalt",
        "Benefits",
        "Kontakt",
    }
)

# Handgepflegte Spalten gibt es nicht mehr. Termine und Notizen von Hand
# nachzutragen war Arbeit, die niemand macht; was wirklich gebraucht wird
# - seit wann eine Bewerbung laeuft - steht ohnehin schon in DynamoDB und
# beantwortet `tracker faellig`.

STELLENLINK = "https://www.arbeitsagentur.de/jobsuche/jobdetail/"

# Name der Quelle, deren Referenznummer in die Oberflaeche der
# Bundesagentur fuehrt - siehe poller/quellen/arbeitsagentur.py. Alte
# Archiveintraege tragen noch gar keine Quelle; sie stammen von dort.
QUELLE_ARBEITSAGENTUR = "arbeitsagentur"

# Bezugspunkt fuer die Entfernung, wenn die Quelle keine mitliefert.
# Derselbe Name, nach dem der Poller sucht.
VORGABE_SUCHORT = "Hamburg"

# Die Schnittstelle hat den Feldnamen schon gewechselt (ADR 0001),
# deshalb beide Schreibweisen.
EXTERNE_URL_FELDER = ("externeURL", "externeUrl")

# Die Endung darf nicht auf einen Punkt hinauslaufen, sonst wandert der
# Schlusspunkt des Satzes in die Adresse: "an jobs@haus.de." ergaebe
# sonst "jobs@haus.de." mit Punkt.
MUSTER_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

# Deutsche Rufnummern in den ueblichen Schreibweisen. Verlangt wird eine
# Mindestlaenge, damit Hausnummern und Jahreszahlen nicht anschlagen.
MUSTER_TELEFON = re.compile(r"(?:\+49|0)\d[\d\s/().-]{6,20}\d")

# Ein Namensbestandteil. Der Punkt fehlt in der Zeichenklasse mit Absicht:
# er beendet den Satz, und "Frau Kern. Wir freuen uns" wuerde sonst als
# dreiteiliger Name gelesen. Titel stehen deshalb als eigene Alternative
# davor.
_NAME = r"[A-ZÄÖÜ][\w-]+"
_TITEL = r"(?:Dr\.|Prof\.)?\s*"

# "Ansprechpartnerin: Frau Meyer", "Ihr Ansprechpartner ist Herr Dr. Kern".
MUSTER_ANSPRECHPARTNER = re.compile(
    rf"Ansprechpartner(?:in)?\w*\s*(?:ist|:|-)?\s*"
    rf"((?:Herrn?|Frau)?\s*{_TITEL}{_NAME}(?:\s+{_NAME}){{0,2}})"
)

MUSTER_ANREDE = re.compile(rf"\b(?:Herrn?|Frau)\s+{_TITEL}{_NAME}(?:\s+{_NAME})?")

# Gehaltsangaben im Fliesstext. Die Strukturfelder der Schnittstelle
# stehen praktisch immer auf KEINE_ANGABEN (ADR 0005), im Text steht
# gemessen bei rund jeder elften Anzeige doch etwas.
#
# Die Spanne zuerst: "55.000 - 65.000 EUR" gehoert ganz in die Zelle,
# nicht nur ihre zweite Haelfte.
_BETRAG = r"\d{2,3}(?:[.\s]\d{3})"
_WAEHRUNG = r"(?:€|Euro|EUR)"

MUSTER_GEHALTSSPANNE = re.compile(
    rf"{_BETRAG}\s*{_WAEHRUNG}?\s*(?:bis|-|–|—)\s*{_BETRAG}\s*{_WAEHRUNG}",
    re.IGNORECASE,
)

MUSTER_GEHALT = re.compile(
    rf"(?:{_BETRAG}\s*{_WAEHRUNG}|{_WAEHRUNG}\s*{_BETRAG}|\d{{2,3}}\s?k\s?{_WAEHRUNG})",
    re.IGNORECASE,
)

# Tarifgruppen des oeffentlichen Dienstes. "E 13" allein waere zu
# unspezifisch, deshalb immer mit dem Tarifwerk oder dem Wort davor.
MUSTER_TARIFGRUPPE = re.compile(
    r"(?:TV(?:Ö|OE|O)D(?:[\s-]?[A-Z]+)?\s*[-–]?\s*(?:E\s?)?\d{1,2}"
    r"|TV[-\s]?L\s*(?:E\s?)?\d{1,2}"
    r"|Entgeltgruppe\s+\d{1,2}"
    r"|\bEG\s?\d{1,2}\b)",
    re.IGNORECASE,
)


def _datum(zeitstempel: int | None) -> str:
    if not zeitstempel:
        return ""
    return datetime.fromtimestamp(zeitstempel, tz=timezone.utc).strftime("%Y-%m-%d")


def _text(wert: Any) -> str:
    return wert.strip() if isinstance(wert, str) else ""


def _oder_leer(wert: Any) -> Any:
    """Zahl oder leere Zelle - nie eine erfundene Null."""
    return "" if wert is None else wert


def firma(roh: dict[str, Any], detail: dict[str, Any]) -> str:
    return _text(roh.get("firma")) or _text(detail.get("arbeitgeber"))


def standort(roh: dict[str, Any], detail: dict[str, Any]) -> str:
    """Postleitzahl und Ort, bei mehreren Standorten die ersten drei."""
    orte: list[str] = []

    for lokation in (roh.get("stellenlokationen") or [])[:3]:
        adresse = lokation.get("adresse") or {}
        ort = _text(adresse.get("ort"))
        if ort:
            orte.append(f"{_text(adresse.get('plz'))} {ort}".strip())

    if not orte:
        for adresse in (detail.get("arbeitsorte") or [])[:3]:
            ort = _text(adresse.get("ort"))
            if ort:
                orte.append(f"{_text(adresse.get('plz'))} {ort}".strip())

    # dict.fromkeys entfernt Doppelte und behaelt die Reihenfolge.
    return " / ".join(dict.fromkeys(orte))


def _erster_ort(roh: dict[str, Any]) -> str:
    for lokation in roh.get("stellenlokationen") or []:
        ort = _text((lokation.get("adresse") or {}).get("ort"))
        if ort:
            return ort
    return ""


def entfernung_km(roh: dict[str, Any]) -> float | None:
    """Entfernung zum Suchort.

    Die Bundesagentur liefert sie im ortsgebundenen Durchgang mit. Die
    uebrigen Quellen nennen nur einen Ortsnamen; daraus wird die
    Luftlinie gerechnet, soweit die Stadt im Verzeichnis steht. Eine
    Region wie "EMEA" ergibt nichts - und braucht auch nichts, denn
    solche Stellen sind ohnehin vollstaendig remote.
    """
    gemeldet = anzeige.entfernung_km(roh)
    if gemeldet is not None:
        return gemeldet

    ort = _erster_ort(roh)
    if not ort:
        return None
    suchort = os.environ.get("JOBSUCHE_WO", "").strip() or VORGABE_SUCHORT
    return entfernung.zwischen(suchort, ort)


def homeoffice(
    roh: dict[str, Any], detail: dict[str, Any] | None = None, text: str = ""
) -> str:
    """Arbeitsmodell aus Schnittstellenfeldern und Anzeigentext.

    Die Einzelheiten stehen in `gemeinsam.homeoffice`. Wichtig hier:
    ohne jede Angabe bleibt die Zelle leer. Frueher stand dort "vor Ort",
    was die Daten nicht hergaben und die Spalte unbrauchbar machte.
    """
    return ho.bestimme(roh or {}, detail or {}, text)


def _kontaktblock(detail: dict[str, Any]) -> dict[str, Any]:
    """Der Kontaktabschnitt der Detailansicht.

    Die Schnittstelle ist inoffiziell und hat Feldnamen waehrend der
    Entwicklung schon einmal gewechselt (ADR 0001). Deshalb werden
    mehrere Namen probiert, statt sich auf einen zu verlassen.
    """
    for name in ("kontakt", "ansprechpartner", "arbeitgeberKontakt"):
        wert = detail.get(name)
        if isinstance(wert, dict):
            return wert
    return {}


def ansprechpartner(detail: dict[str, Any], text: str | None = None) -> str:
    """Name aus den Kontaktfeldern, sonst aus dem Anzeigentext.

    Der Griff in den Text ist eine Heuristik und liegt deshalb in einer
    Spalte, die der Export nur vorbelegt. `text` kann den Anzeigentext
    mitbringen, wenn er nicht in der Detailansicht steht, sondern - wie
    bei den uebrigen Quellen - schon in der Anzeige selbst.
    """
    block = _kontaktblock(detail)
    teile = [_text(block.get(name)) for name in ("anrede", "titel", "vorname", "nachname")]
    aus_feldern = " ".join(teil for teil in teile if teil)
    if aus_feldern:
        return aus_feldern
    if _text(block.get("name")):
        return _text(block.get("name"))

    beschreibung = text if text is not None else anzeige.beschreibung(detail)
    treffer = MUSTER_ANSPRECHPARTNER.search(beschreibung)
    if treffer:
        return " ".join(treffer.group(1).split())
    treffer = MUSTER_ANREDE.search(beschreibung)
    return " ".join(treffer.group(0).split()) if treffer else ""


def kontakt(detail: dict[str, Any], text: str | None = None) -> str:
    block = _kontaktblock(detail)
    beschreibung = text if text is not None else anzeige.beschreibung(detail)

    mail = next(
        (_text(block.get(n)) for n in ("email", "mail", "eMail") if _text(block.get(n))),
        "",
    )
    if not mail:
        treffer = MUSTER_EMAIL.search(beschreibung)
        mail = treffer.group(0) if treffer else ""

    telefon = next(
        (
            _text(block.get(n))
            for n in ("telefon", "telefonnummer", "tel", "rufnummer")
            if _text(block.get(n))
        ),
        "",
    )
    if not telefon:
        treffer = MUSTER_TELEFON.search(beschreibung)
        telefon = " ".join(treffer.group(0).split()) if treffer else ""

    return " / ".join(teil for teil in (mail, telefon) if teil)


def kontakt_gesamt(detail: dict[str, Any], text: str | None = None) -> str:
    """Ansprechpartner und Erreichbarkeit in einer Zelle.

    Frueher zwei Spalten - der Name stand selten ohne die Mail daneben,
    und beides zusammen ist kuerzer als zwei halbleere Spalten.
    """
    teile = [ansprechpartner(detail, text), kontakt(detail, text)]
    return " · ".join(teil for teil in teile if teil)


def externe_url(roh: dict[str, Any], detail: dict[str, Any]) -> str:
    for feld in EXTERNE_URL_FELDER:
        wert = _text(roh.get(feld)) or _text(detail.get(feld))
        if wert:
            return wert
    return ""


def quelle(roh: dict[str, Any]) -> str:
    """Welches Portal die Anzeige gemeldet hat."""
    return _text(roh.get("quelle")) or QUELLE_ARBEITSAGENTUR


def stellenlink(
    referenznummer: str, roh: dict[str, Any], detail: dict[str, Any]
) -> str:
    """Adresse, unter der die Anzeige zu lesen ist.

    Bei der Bundesagentur fuehrt die Referenznummer in ihre eigene
    Oberflaeche. Die uebrigen Portale haben dort nichts stehen - fuer sie
    ist die mitgelieferte Adresse der einzige Weg zur Anzeige.
    """
    if quelle(roh) != QUELLE_ARBEITSAGENTUR:
        extern = externe_url(roh, detail)
        if extern:
            return extern
    return f"{STELLENLINK}{referenznummer}"


def bewerbungsweg(
    roh: dict[str, Any], detail: dict[str, Any], text: str | None = None
) -> str:
    """Nur ein Kanal, der von der Jobboerse abweicht.

    Die Bewerbung "ueber die Jobboerse der Arbeitsagentur" trifft auf die
    grosse Mehrheit zu und stand deshalb in fast jeder Zeile gleich. Eine
    Zelle, die nichts unterscheidet, bleibt jetzt leer.
    """
    if externe_url(roh, detail):
        return "Online-Portal des Arbeitgebers"
    if MUSTER_EMAIL.search(kontakt(detail, text)):
        return "E-Mail"
    return ""


def gehalt(roh: dict[str, Any], detail: dict[str, Any], text: str = "") -> str:
    """Angabe aus der Anzeige, sonst der Tarifvertrag, sonst aus dem Text.

    Die Anzeigen schweigen meist: `verguetungsangabe` steht bei den
    beobachteten Treffern durchgaengig auf KEINE_ANGABEN (ADR 0005).
    Ein regionaler Median aus dem Entgeltatlas stand hier einmal als
    Rueckfall - er war fuer jede Anzeige einer Berufsklasse derselbe und
    sagte nichts ueber die konkrete Stelle. Wer eine Einordnung braucht,
    fragt `salary-check` gezielt. Was im Anzeigentext steht, gilt
    dagegen fuer genau diese Stelle - das wird gelesen.
    """
    angabe = _text(detail.get("verguetung"))
    if angabe:
        return angabe

    tarif = _text(detail.get("tarifvertrag")) or _text(roh.get("tarifvertrag"))
    if tarif:
        return f"nach Tarifvertrag ({tarif})"

    return gehalt_aus_text(text)


def gehalt_aus_text(text: str) -> str:
    """Betrag oder Tarifgruppe aus dem Anzeigentext.

    Eine Heuristik wie die Kontaktsuche, und wie diese nur ein Vorschlag.
    Gefunden wird bei rund neun Prozent der Anzeigen etwas - wenig, aber
    mehr als die Strukturfelder hergeben, die schlicht leer sind.
    """
    if not text:
        return ""

    for muster in (MUSTER_GEHALTSSPANNE, MUSTER_GEHALT):
        treffer = muster.search(text)
        if treffer:
            return " ".join(treffer.group(0).split())

    treffer = MUSTER_TARIFGRUPPE.search(text)
    return " ".join(treffer.group(0).split()) if treffer else ""


def zeile(
    eintrag: Any,
    roh: dict[str, Any] | None = None,
    detail: dict[str, Any] | None = None,
    bewertung: Any = None,
) -> dict[str, Any]:
    """Eine Anzeige als Zuordnung von Spaltenname auf Zellinhalt.

    Die Nummer fehlt bewusst - sie ergibt sich erst aus der Stellung in
    der fertigen Tabelle und wird dort vergeben. Die Passungsspalten
    fehlen, solange kein Profil vorliegt; dann werden sie auch nicht
    angelegt.
    """
    roh = roh or {}
    detail = detail or {}
    # Bei der Bundesagentur steht der Text in der Detailansicht, bei den
    # uebrigen Quellen schon in der Anzeige. Einmal bestimmen, ueberall
    # verwenden.
    text = anzeige.beschreibung(detail, roh)

    werte: dict[str, Any] = {
        SPALTE_REFERENZ: eintrag.referenznummer,
        "Firma": firma(roh, detail),
        "Position": _text(roh.get("stellenangebotsTitel")) or eintrag.titel,
        "Link zur Ausschreibung": stellenlink(eintrag.referenznummer, roh, detail),
        "Standort": standort(roh, detail),
        "Homeoffice-Modell": homeoffice(roh, detail, text),
        "Gehalt": gehalt(roh, detail, text),
        "Benefits": benefits.als_text(text),
        "Kontakt": kontakt_gesamt(detail, text),
        "Status": st.text(eintrag.status),
        "Quelle": quelle(roh),
        # None statt 0 - eine Anzeige ohne Datumsangabe ist nicht
        # taggleich veroeffentlicht, sondern unbekannt alt.
        "Alter (Tage)": _oder_leer(anzeige.alter_tage(roh)),
        "Entfernung (km)": _oder_leer(entfernung_km(roh)),
    }

    if bewertung is not None:
        werte["Passung"] = bewertung.stufe
        # Als Zahl, nicht als Text - sonst sortiert Excel 9 hinter 80.
        werte["Punkte"] = bewertung.punkte if bewertung.brauchbar else ""
        werte["Treffer"] = bewertung.treffertext
        werte["Lücken"] = bewertung.lueckentext

    return werte
