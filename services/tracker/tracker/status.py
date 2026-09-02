"""Zustaende einer Bewerbung."""
from __future__ import annotations

GEFUNDEN = "GEFUNDEN"
BEWORBEN = "BEWORBEN"
INTERVIEW = "INTERVIEW"
ZUSAGE = "ZUSAGE"
ABSAGE = "ABSAGE"

# Reihenfolge wie im Bewerbungsverlauf, nicht alphabetisch - sie bestimmt
# die Sortierung in der Uebersicht.
ALLE = (GEFUNDEN, BEWORBEN, INTERVIEW, ZUSAGE, ABSAGE)

# Zustaende, bei denen die Sache erledigt ist.
ABGESCHLOSSEN = (ZUSAGE, ABSAGE)


class UnbekannterStatus(ValueError):
    """Ein Status, den der Tracker nicht kennt."""


def pruefe(status: str) -> str:
    """Normalisiert die Eingabe und weist Unbekanntes ab."""
    normalisiert = status.strip().upper()
    if normalisiert not in ALLE:
        erlaubt = ", ".join(ALLE)
        raise UnbekannterStatus(f"{status!r} ist unbekannt. Erlaubt sind: {erlaubt}")
    return normalisiert


def ist_verfolgt(status: str) -> bool:
    """Wurde die Anzeige ueber das blosse Finden hinaus angefasst?

    Nur gefundene Anzeigen darf die Tabelle nach Ablauf der Frist
    vergessen. Sobald eine Bewerbung laeuft, gehoert der Eintrag
    dauerhaft erhalten.
    """
    return status != GEFUNDEN
