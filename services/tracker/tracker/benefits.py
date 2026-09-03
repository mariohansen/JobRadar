"""Erkennung von Zusatzleistungen im Anzeigentext.

Bewusst ein festes Stichwortverzeichnis statt einer Sprachanalyse: die
Begriffe sind in Stellenanzeigen weitgehend standardisiert, das Ergebnis
ist nachvollziehbar und der Lauf kostet nichts. Was nicht in der Liste
steht, wird nicht gefunden - das ist der Preis und der Grund, warum die
Spalte im Export nur vorbelegt und nicht ueberschrieben wird.

Umlaute stehen als Platzhalter in den Mustern. Anzeigentexte kommen aus
allen moeglichen Redaktionssystemen; "vermögenswirksam" und
"vermoegenswirksam" meinen dasselbe, und ein Muster, das nur eine der
Schreibweisen kennt, findet die Haelfte nicht.
"""
from __future__ import annotations

import re

# Platzhalter -> Alternativen, laengste zuerst. Ohne diese Reihenfolge
# wuerde bei "vermoegens" schon das blosse o greifen und der Rest des
# Musters ins Leere laufen.
UMLAUTE = {
    "{ae}": "(?:ae|ä|a)",
    "{oe}": "(?:oe|ö|o)",
    "{ue}": "(?:ue|ü|u)",
}

# Bezeichnung -> Muster, das sie ausloest. Die Reihenfolge bestimmt die
# Reihenfolge in der Ausgabe; das Wichtigste zuerst. Homeoffice fehlt
# absichtlich - dafuer gibt es eine eigene Spalte mit dem Prozentwert,
# der belastbarer ist als jede Erwaehnung im Fliesstext.
KATALOG: tuple[tuple[str, str], ...] = (
    ("Unbefristet", r"unbefristet"),
    ("Tarifvertrag", r"tarifvertrag|tarifvertraglich|tv{oe}d|tv-l\b|nach tarif"),
    ("Gleitzeit", r"gleitzeit|flexible arbeitszeit|vertrauensarbeitszeit|arbeitszeitkonto"),
    ("Teilzeit möglich", r"teilzeit"),
    # Erst ab 30 Tagen ist Urlaub ein Argument; darunter ist es der
    # gesetzliche Rahmen und gehoert nicht in die Spalte.
    ("30+ Tage Urlaub", r"\b(?:3\d|[4-9]\d)\s*(?:tage\s+)?urlaub"),
    ("Betriebliche Altersvorsorge", r"betriebliche(?:n|r)? altersvorsorge|\bbav\b|altersvorsorge"),
    ("Vermögenswirksame Leistungen", r"verm{oe}gens?wirksame leistungen|\bvwl\b"),
    (
        "Bonus / Sonderzahlung",
        r"erfolgsbeteiligung|gewinnbeteiligung|weihnachtsgeld|urlaubsgeld"
        r"|13\.\s*monatsgehalt|sonderzahlung|pr{ae}mie|\bbonus",
    ),
    (
        "Jobticket / ÖPNV",
        r"jobticket|job-ticket|deutschlandticket|hvv[- ]?(?:card|ticket|profi)"
        r"|fahrtkostenzuschuss|\b{oe}pnv",
    ),
    ("Jobrad / Bikeleasing", r"jobrad|job-rad|bikeleasing|bike-leasing|dienstrad|fahrradleasing"),
    ("Firmenwagen", r"firmenwagen|dienstwagen|firmenfahrzeug"),
    (
        "Weiterbildung",
        r"weiterbildung|fortbildung|schulungsbudget|zertifizierung"
        r"|entwicklungsm{oe}glichkeit|weiterentwicklung",
    ),
    (
        "Sport / Gesundheit",
        r"urban sports|wellpass|qualitrain|hansefit|fitnessstudio"
        r"|gesundheitsf{oe}rderung|betriebssport",
    ),
    (
        "Kantine / Verpflegung",
        r"kantine|betriebsrestaurant|essenszuschuss|essensgeld|obst und getr{ae}nke"
        r"|kostenlose getr{ae}nke",
    ),
    (
        "Kinderbetreuung",
        r"kinderbetreuung|betriebskita|kita[- ]?(?:platz|zuschuss)|betriebskinderg{ae}rten",
    ),
    (
        "Mitarbeiterrabatte",
        r"mitarbeiterrabatt|personalrabatt|corporate benefits|mitarbeiterverg{ue}nstigung",
    ),
    ("Sabbatical", r"sabbatical"),
    ("Firmenevents", r"firmenevent|teamevent|betriebsausflug|sommerfest"),
    ("Parkplatz", r"parkplatz|parkpl{ae}tze|firmenparkplatz"),
    ("Umzugshilfe", r"umzugshilfe|umzugskosten|relocation"),
)


def entfalte(muster: str) -> str:
    for platzhalter, alternativen in UMLAUTE.items():
        muster = muster.replace(platzhalter, alternativen)
    return muster


_UEBERSETZT = tuple(
    (bezeichnung, re.compile(entfalte(muster), re.IGNORECASE))
    for bezeichnung, muster in KATALOG
)


def finde(text: str) -> list[str]:
    """Alle Zusatzleistungen, die der Text nennt."""
    if not text:
        return []
    return [bezeichnung for bezeichnung, muster in _UEBERSETZT if muster.search(text)]


def als_text(text: str) -> str:
    return ", ".join(finde(text))
