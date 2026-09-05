"""Titelbegriffe, die eine Anzeige aussortieren.

Der Poller sucht breit nach Stellenbezeichnungen; hier faellt heraus,
was formal zum Suchbegriff passt, aber nicht zur Lebenslage: Praktika
und Werkstudentenstellen, die unter denselben Berufsbegriffen laufen,
und die Erfahrungsstufen ober- und unterhalb der angepeilten.

Ein Ort statt zweier: der `filter-dedup` entscheidet damit, was in die
Mail kommt, der `tracker`, was in die Tabelle kommt. Liefen die Listen
auseinander, zeigte die Tabelle Anzeigen, die die Mail zu Recht
verschwiegen hat.

Verglichen wird auf den **Wortanfang**. Reine Teilzeichenketten waeren
bei kurzen Begriffen gefaehrlich - "sr" steckt auch in "Israel". Das
Wortende bleibt offen, damit "praktikum" auch "Praktikumsstelle" trifft.
"""
from __future__ import annotations

import re
from typing import Any

# Drei Gruppen:
#
# Lebenslage: Praktikum, Werkstudent und Aehnliches.
#
# Erfahrungsstufe: "senior" und "sr". "sr" deckt auch "Sr." ab, ohne in
# "Israel" anzuschlagen, weil nur der Wortanfang zaehlt.
#
# Fuehrungsrollen: "lead" erfasst auch "Leader", braucht aber "teamlead"
# als eigenen Eintrag, weil dort kein Wortanfang steht. Dasselbe gilt
# fuer "leiter" und "teamleiter".
#
# Bewusst nicht dabei: "manager" - der Begriff steht auch in Titeln wie
# "Junior Customer Success Manager" und wuerde Einstiegsstellen treffen.
STANDARD: tuple[str, ...] = (
    "praktikum",
    "werkstudent",
    "ausbildung",
    "minijob",
    "aushilfe",
    "schulpraktikum",
    "senior",
    "sr",
    "lead",
    "teamlead",
    "leiter",
    "teamleiter",
    "principal",
    "staff",
    "head of",
    # Fachrichtungen, die nichts mit dem angepeilten Profil zu tun haben.
    # Sie kommen ueber die breiten Suchbegriffe herein: eine Suche nach
    # "Developer" oder "Java" liefert auch Embedded- und SAP-Rollen.
    "c++",
    "embedded",
    "sap",
)

# Arbeitgeber, von denen nichts kommen soll - eine persoenliche Liste,
# kein fachliches Kriterium. Sie steht getrennt, weil sie ein anderes
# Feld prueft: den Firmennamen, nicht den Titel.
#
# Ein Eintrag deckt alle Firmierungen ab, die so beginnen. "ntt data"
# trifft damit sowohl die "NTT DATA Deutschland SE" als auch die
# "NTT DATA Business Solutions Global Managed Services GmbH".
#
# Ueber MATCH_ARBEITGEBER_AUSSCHLUSS zu aendern.
ARBEITGEBER: tuple[str, ...] = (
    "ntt data",
)


def enthaelt(text: str, begriff: str) -> bool:
    """Kommt der Begriff am Anfang eines Wortes vor?"""
    return re.search(r"\b" + re.escape(begriff), text) is not None


def grund(text: str, begriffe: tuple[str, ...] = STANDARD) -> str | None:
    """Der erste Ausschlussbegriff, der im Text steht - sonst None."""
    if not text:
        return None
    gesenkt = text.lower()
    return next((begriff for begriff in begriffe if enthaelt(gesenkt, begriff)), None)


def arbeitgeber_grund(
    firma: Any, begriffe: tuple[str, ...] = ARBEITGEBER
) -> str | None:
    """Der Ausschlussgrund zu einem Firmennamen, sonst None.

    Getrennt von `grund`, weil hier der Arbeitgeber geprueft wird und
    nicht der Titel. Ein Titelfilter faenge "NTT DATA" heute zwar auch,
    weil eine Quelle den Firmennamen in den Titel schreibt - aber das
    ist deren Formatierung und keine Zusage.
    """
    if not isinstance(firma, str) or not firma.strip():
        return None
    gesenkt = firma.casefold()
    return next((begriff for begriff in begriffe if enthaelt(gesenkt, begriff)), None)


def _liste(roh: str | None) -> tuple[str, ...]:
    return tuple(teil.strip().lower() for teil in (roh or "").split(",") if teil.strip())


def aus_umgebung(roh: str | None) -> tuple[str, ...]:
    """Die Titelbegriffe aus MATCH_AUSSCHLUSS, oder die Vorgabe.

    Leer oder nicht gesetzt bedeutet: die Standardliste. Damit lesen
    `filter-dedup` und `tracker` dieselbe Einstellung.
    """
    return _liste(roh) or STANDARD


def arbeitgeber_aus_umgebung(roh: str | None) -> tuple[str, ...]:
    """Die Arbeitgeber aus MATCH_ARBEITGEBER_AUSSCHLUSS, oder die Vorgabe."""
    return _liste(roh) or ARBEITGEBER
