"""Felder, die mehr als ein Dienst aus einer Anzeige liest.

Der filter-dedup braucht sie, um neue Anzeigen fuer die Mail
anzureichern, der tracker fuer die Spalten der Tabelle. Beide sollen
dasselbe herauslesen.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

# In dieser Reihenfolge geprueft: das erste Datum ist das der ersten
# Veroeffentlichung, das zweite das der letzten Aktualisierung. Fuer die
# Frage "wie lange steht das schon da" zaehlt das erste.
DATUMSFELDER = (
    "datumErsteVeroeffentlichung",
    "aktuelleVeroeffentlichungsdatum",
    "modifikationsTimestamp",
)

# Die Schnittstelle hat Feldnamen schon einmal gewechselt (ADR 0001),
# deshalb mehrere Kandidaten statt eines.
ENTFERNUNGSFELDER = ("entfernung", "distanz", "entfernungKm")

# Der Anzeigentext der Detailansicht. Die Schnittstelle hat das Feld von
# `stellenbeschreibung` auf `stellenangebotsBeschreibung` umbenannt - ohne
# den neuen Namen bleibt jede Anzeige "zu wenig Angaben". Der alte Name
# steht als Rueckfallebene dahinter.
BESCHREIBUNGSFELDER = ("stellenangebotsBeschreibung", "stellenbeschreibung")

# Die Adresse der Anzeige beim Arbeitgeber oder Portal. Auch hier hat die
# Schnittstelle die Schreibweise gewechselt.
EXTERNE_URL_FELDER = ("externeURL", "externeUrl")

# Nur bei dieser Quelle fuehrt die Referenznummer in eine Oberflaeche.
# Muss zum Namen in poller/quellen/arbeitsagentur.py passen.
QUELLE_ARBEITSAGENTUR = "arbeitsagentur"

STELLENLINK = "https://www.arbeitsagentur.de/jobsuche/jobdetail/"


def _text(wert: Any) -> str:
    return wert.strip() if isinstance(wert, str) else ""


def titel(job: dict[str, Any]) -> str:
    return _text(job.get("stellenangebotsTitel"))


def beschreibung(*quellen: dict[str, Any] | None) -> str:
    """Anzeigentext, aus der ersten Quelle die einen hat.

    Zwei Faelle: bei der Bundesagentur steht der Text nur in der
    Detailansicht, die einzeln abgerufen werden muss. Die uebrigen
    Portale liefern ihn schon in der Trefferliste mit - dort steht er
    also in der Anzeige selbst. Beide Stellen werden geprueft, in der
    uebergebenen Reihenfolge.
    """
    for quelle in quellen:
        for feld in BESCHREIBUNGSFELDER:
            wert = _text((quelle or {}).get(feld))
            if wert:
                return wert
    return ""


def quelle(job: dict[str, Any] | None) -> str:
    """Welches Portal die Anzeige gemeldet hat.

    Eintraege aus der Zeit vor den zusaetzlichen Quellen tragen das Feld
    noch nicht; sie stammen von der Bundesagentur.
    """
    wert = _text((job or {}).get("quelle"))
    return wert or QUELLE_ARBEITSAGENTUR


def externe_url(job: dict[str, Any] | None, detail: dict[str, Any] | None = None) -> str:
    for feld in EXTERNE_URL_FELDER:
        wert = _text((job or {}).get(feld)) or _text((detail or {}).get(feld))
        if wert:
            return wert
    return ""


def stellenlink(
    job: dict[str, Any] | None,
    detail: dict[str, Any] | None = None,
    referenznummer: str = "",
) -> str:
    """Adresse, unter der die Anzeige zu lesen ist.

    Bei der Bundesagentur fuehrt die Referenznummer in ihre eigene
    Oberflaeche - und die zeigt den vollstaendigen Text, den die
    Trefferliste nicht mitgibt. Deshalb bleibt es dort bei diesem Link,
    auch wenn eine externe Adresse danebensteht.

    Die uebrigen Portale haben bei der Bundesagentur nichts stehen. Fuer
    sie ist die mitgelieferte Adresse der einzige Weg zur Anzeige; ein
    Jobboerse-Link mit "arbeitnow:..." im Pfad laeuft ins Leere.
    """
    job = job or {}
    if quelle(job) != QUELLE_ARBEITSAGENTUR:
        extern = externe_url(job, detail)
        if extern:
            return extern

    nummer = referenznummer or _text(job.get("referenznummer"))
    return f"{STELLENLINK}{nummer}"


def text(roh: dict[str, Any], detail: dict[str, Any] | None = None) -> str:
    """Alles, worin eine Anforderung stehen kann.

    Ohne Detailansicht bleiben nur Titel und Berufsbezeichnungen - fuer
    eine Passungsbewertung meist zu wenig, was diese dann auch sagt.
    """
    teile = [
        _text(roh.get("stellenangebotsTitel")),
        _text(roh.get("hauptberuf")),
        *(_text(b) for b in (roh.get("alleBerufe") or [])),
        beschreibung(detail, roh),
    ]
    return "\n".join(teil for teil in teile if teil)


def _als_datum(wert: Any) -> date | None:
    roh = _text(wert)
    if not roh:
        return None
    # Die API liefert mal "2026-08-25", mal einen vollen Zeitstempel.
    try:
        return datetime.fromisoformat(roh.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def veroeffentlicht_am(job: dict[str, Any]) -> date | None:
    for feld in DATUMSFELDER:
        gefunden = _als_datum(job.get(feld))
        if gefunden:
            return gefunden
    return None


def alter_tage(job: dict[str, Any], heute: date | None = None) -> int | None:
    """Wie lange die Anzeige schon steht.

    Eine Anzeige, die seit Wochen laeuft, ist haeufig laengst besetzt
    oder die Stelle ist schwer zu besetzen - beides ist beim Sortieren
    nuetzlich zu wissen.
    """
    veroeffentlicht = veroeffentlicht_am(job)
    if veroeffentlicht is None:
        return None
    tage = ((heute or date.today()) - veroeffentlicht).days
    # Ein in der Zukunft liegendes Datum ist ein Datenfehler, kein
    # negatives Alter.
    return max(0, tage)


def entfernung_km(job: dict[str, Any]) -> float | None:
    """Entfernung zum Suchort, bei mehreren Standorten die kuerzeste.

    Kommt nur aus dem ortsgebundenen Durchgang des Pollers. Der
    bundesweite Durchgang sucht ohne `wo`, dort gibt es keinen Bezugs-
    punkt und damit keine Entfernung - was fuer eine vollstaendig
    remote zu erledigende Stelle auch niemanden stoeren muss.
    """
    werte: list[float] = []

    for feld in ENTFERNUNGSFELDER:
        wert = job.get(feld)
        if isinstance(wert, (int, float)) and wert >= 0:
            werte.append(float(wert))

    for lokation in job.get("stellenlokationen") or []:
        for feld in ENTFERNUNGSFELDER:
            wert = lokation.get(feld)
            if isinstance(wert, (int, float)) and wert >= 0:
                werte.append(float(wert))

    return round(min(werte), 1) if werte else None
