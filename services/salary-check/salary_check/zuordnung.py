"""Zuordnung einer Stellenanzeige zu einem KldB-Schluessel.

Die Jobsuche liefert Berufsbezeichnungen im Klartext, der Entgeltatlas
erwartet einen Schluessel der Klassifikation der Berufe. Dazwischen liegt
eine Heuristik - eine belastbare Zuordnung gaebe es nur ueber die
Berufedatenbank der Bundesagentur, was fuer diesen Zweck
unverhaeltnismaessig waere.

Der Schluessel besteht aus der vierstelligen Berufsgruppe und einer
fuenften Ziffer fuer das Anforderungsniveau:
1 Helfer, 2 Fachkraft, 3 Spezialist, 4 Experte.
"""
from __future__ import annotations

# Berufsgruppen der Klassifikation der Berufe 2010.
GRUPPE_SOFTWAREENTWICKLUNG = "4341"
GRUPPE_IT_ANWENDUNGSBERATUNG = "4321"

# Begriffe, die im Titel auf ein Anforderungsniveau hindeuten.
HINWEIS_EXPERTE = ("senior", "lead", "principal", "architekt", "architect", "head of")
HINWEIS_FACHKRAFT = ("junior", "einsteiger", "berufseinsteiger", "trainee")

# Begriffe, die auf die Beratungs- statt die Entwicklungsschiene deuten.
HINWEIS_BERATUNG = ("consultant", "berater", "sap", "servicenow", "salesforce")


def niveau_aus_titel(titel: str) -> str:
    text = titel.lower()
    if any(begriff in text for begriff in HINWEIS_EXPERTE):
        return "4"
    if any(begriff in text for begriff in HINWEIS_FACHKRAFT):
        return "2"
    # Ohne Hinweis: Spezialist als mittlere Annahme. Fuer Stellen, die ein
    # Studium voraussetzen, ist das eher zu niedrig gegriffen - eine zu
    # optimistische Angabe waere hier der unangenehmere Fehler.
    return "3"


def gruppe_aus_titel(titel: str) -> str:
    text = titel.lower()
    if any(begriff in text for begriff in HINWEIS_BERATUNG):
        return GRUPPE_IT_ANWENDUNGSBERATUNG
    return GRUPPE_SOFTWAREENTWICKLUNG


def kldb_aus_titel(titel: str) -> str:
    """Fuenfstelliger Schluessel fuer eine Stellenbezeichnung."""
    return gruppe_aus_titel(titel) + niveau_aus_titel(titel)
