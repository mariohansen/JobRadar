"""Fachbegriffe finden, die das Verzeichnis noch nicht kennt.

Das Faehigkeitsverzeichnis ist eine feste Liste (faehigkeiten.py). Das
macht die Bewertung nachvollziehbar und kostenlos, hat aber einen blinden
Fleck: was nicht darin steht, wird nicht gefunden - und taucht deshalb
auch im Skill-Trend nicht auf. Verlangt der Markt seit einem halben Jahr
etwas, das niemand eingetragen hat, merkt man es nie.

Hier werden deshalb Kandidaten gesammelt: Woerter aus den Anzeigentexten,
die *wie* eine Technologie aussehen und im Verzeichnis fehlen. Das ist
ausdruecklich ein Vorschlagswesen, keine Erkennung - was davon wirklich
hineingehoert, entscheidet ein Mensch.

Erkannt wird an der Schreibweise, nicht an der Bedeutung:

* Abkuerzungen in Grossbuchstaben - ETL, AWS, SAP, gRPC,
* Binnenmajuskeln - PostgreSQL, TypeScript, DevOps, GitLab,
* Namen mit Punkt oder Plus - Node.js, C++, .NET.

Deutsche Substantive sind auch gross geschrieben, deshalb reicht der
erste Buchstabe allein nicht - es braucht einen zweiten Grossbuchstaben,
eine reine Versalienschreibung oder ein Sonderzeichen.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from . import faehigkeiten as fk

# Abkuerzungen: zwei bis sechs Grossbuchstaben, optional mit Ziffern.
# Ein fuehrender Kleinbuchstabe ist erlaubt, damit gRPC und iOS
# mitkommen.
ABKUERZUNG = re.compile(r"\b[a-z]?[A-Z]{2,6}[0-9]{0,2}\b")

# Binnenmajuskel: ein Grossbuchstabe mitten im Wort.
BINNENMAJUSKEL = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+\b")

# Namen mit Sonderzeichen, die kein normales Wort haben kann.
SONDERNAME = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:\.js|\.NET|\+\+|#)\B|\b\.NET\b")

MUSTER = (ABKUERZUNG, BINNENMAJUSKEL, SONDERNAME)

# Was die Muster zuverlaessig faelschlich einsammeln: Rechtsformen,
# Anreden, Bundeslaender, Floskeln aus Stellenanzeigen und die ueblichen
# Abkuerzungen des Arbeitsrechts. Ohne diese Liste besteht die Ausgabe
# zur Haelfte aus "GmbH" und "m/w/d".
STOPPWOERTER = frozenset(
    {
        # Rechtsform und Firmierung
        "GMBH", "MBH", "AG", "KG", "OHG", "GBR", "UG", "SE", "CO", "INC",
        "LTD", "LLC", "PLC", "NV", "BV", "EV", "EK", "GMBHCOKG",
        # Stellenanzeigen-Floskeln
        "MWD", "WMD", "DMW", "MFD", "GN", "DIV", "FTE", "HR", "CV",
        "ASAP", "PDF", "DOC", "URL", "WWW", "HTTP", "HTTPS",
        # Arbeitsrecht und Soziales
        "TVOD", "TVL", "BAV", "VWL", "OPNV", "HVV", "BGM", "SGB", "AGG",
        "EUR", "USD", "CHF", "MWST", "USTG", "DSGVO", "GDPR",
        # Regionen und Anreden
        "NRW", "BW", "DE", "EU", "US", "USA", "UK", "APAC", "EMEA", "DACH",
        "HH", "HB", "SH", "MV", "RLP", "LSA", "ST", "TH", "BB", "BY",
        # Allgemeines
        "ZB", "BZW", "USW", "UVM", "INKL", "EXKL", "CA", "NR", "ABS",
        "OK", "IT", "KI", "AI",
        # Haelften bekannter Begriffe. Das Verzeichnis kennt "CI/CD" als
        # Ganzes; die Mustersuche hier zerlegt am Schraegstrich und
        # meldete sonst zwei angebliche Neuentdeckungen je Anzeige.
        "CI", "CD",
        # Der Katalog kennt ".NET" als Schreibweise von C#; die
        # Mustersuche traegt den Punkt nicht mit.
        "NET",
        # Deutsche Woerter aus Versalien-Ueberschriften ("DEINE AUFGABEN
        # BEI UNS"). Ohne sie besteht die halbe Liste aus Fuellwoertern.
        "DER", "DIE", "DAS", "DEM", "DEN", "DES", "EIN", "EINE",
        "UND", "ODER", "ABER", "MIT", "OHNE", "FUER", "FÜR", "VON", "VOM",
        "BEI", "BEIM", "AUF", "AUS", "NACH", "ZUM", "ZUR", "UEBER", "ÜBER",
        "WIR", "UNS", "UNSER", "UNSERE", "DEIN", "DEINE", "IHR", "IHRE",
        "DIR", "SIE", "ALS", "IST", "SIND", "HAST", "HAT", "WIRD",
        "WAS", "WER", "WIE", "WO", "DU", "ALLE", "MEHR", "NEU", "JETZT",
        "JOB", "JOBS", "TEAM", "NEWS", "TOP", "PLUS", "HOME", "OFFICE",
    }
)

# Ab wie vielen Zeichen ein Treffer ueberhaupt interessant ist.
MINDESTLAENGE = 2


def _bekannt() -> set[str]:
    """Alles, was das Verzeichnis schon erkennt - in Vergleichsform."""
    return {name.casefold() for name in fk.KATEGORIE_VON}


def kandidaten(text: str, bekannt: set[str] | None = None) -> set[str]:
    """Technologieverdaechtige Woerter eines Textes, ohne die bekannten.

    Als Menge, nicht als Liste: fuer die Frage "in wie vielen Anzeigen
    kommt das vor" zaehlt jede Anzeige einmal, egal wie oft das Wort
    darin steht.
    """
    if not text:
        return set()

    bekannt = _bekannt() if bekannt is None else bekannt
    gefunden: set[str] = set()

    for muster in MUSTER:
        for treffer in muster.findall(text):
            wort = treffer.strip(".,;:()[]{}\"'")
            if len(wort) < MINDESTLAENGE:
                continue
            if wort.upper().replace(".", "").replace("-", "") in STOPPWOERTER:
                continue
            if wort.casefold() in bekannt:
                continue
            # Der Katalog kennt manche Begriffe unter anderem Namen
            # ("dotnet" fuer C#). Wer schon anschlaegt, ist nicht neu.
            if fk.finde(wort):
                continue
            gefunden.add(wort)

    return gefunden


def zaehle(texte: Iterable[str]) -> Counter:
    """In wie vielen Texten jeder Kandidat vorkommt."""
    bekannt = _bekannt()
    gezaehlt: Counter = Counter()
    for text in texte:
        gezaehlt.update(kandidaten(text, bekannt))
    return gezaehlt
