"""Zustaende einer Bewerbung.

Gepflegt werden sie in der Tabelle selbst: die Spalte "Status" hat ein
Auswahlfeld, und der naechste Export liest die Auswahl zurueck nach
DynamoDB. Der Umweg ueber `tracker setze` bleibt moeglich, ist aber
nicht mehr der Regelweg - wer ohnehin in der Tabelle sitzt, soll dort
klicken koennen.
"""
from __future__ import annotations

GEFUNDEN = "GEFUNDEN"
BEWORBEN = "BEWORBEN"
INTERVIEW = "INTERVIEW"
ZUSAGE = "ZUSAGE"
ABSAGE = "ABSAGE"
UNINTERESSANT = "UNINTERESSANT"

# Reihenfolge wie im Bewerbungsverlauf, nicht alphabetisch - sie bestimmt
# die Sortierung in der Uebersicht.
ALLE = (GEFUNDEN, BEWORBEN, INTERVIEW, ZUSAGE, ABSAGE, UNINTERESSANT)

# Zustaende, bei denen die Sache erledigt ist.
ABGESCHLOSSEN = (ZUSAGE, ABSAGE, UNINTERESSANT)

# Eine laufende Bewerbung - hier haengt Arbeit dran.
LAEUFT = (BEWORBEN, INTERVIEW, ZUSAGE)

# Was in der Tabelle steht. GEFUNDEN bleibt leer: es ist kein Zustand,
# den jemand gesetzt hat, sondern der Ausgangspunkt - und eine Spalte,
# in der dreihundertmal dasselbe steht, traegt nichts bei.
TEXT = {
    GEFUNDEN: "",
    BEWORBEN: "Abgeschickt",
    INTERVIEW: "Interview",
    ZUSAGE: "Zusage",
    ABSAGE: "Absage",
    UNINTERESSANT: "Nicht interessant",
}

# Die Auswahl im Tabellenfeld, in der Reihenfolge des Verlaufs.
AUSWAHL = tuple(TEXT[s] for s in (BEWORBEN, INTERVIEW, ZUSAGE, ABSAGE, UNINTERESSANT))

_AUS_TEXT = {text.casefold(): status for status, text in TEXT.items() if text}


class UnbekannterStatus(ValueError):
    """Ein Status, den der Tracker nicht kennt."""


def pruefe(status: str) -> str:
    """Normalisiert die Eingabe und weist Unbekanntes ab.

    Angenommen wird beides: der interne Name (BEWORBEN) und der Text aus
    der Tabelle (Abgeschickt).
    """
    roh = status.strip()
    if roh.upper() in ALLE:
        return roh.upper()
    aus_tabelle = _AUS_TEXT.get(roh.casefold())
    if aus_tabelle:
        return aus_tabelle

    erlaubt = ", ".join(ALLE)
    raise UnbekannterStatus(f"{status!r} ist unbekannt. Erlaubt sind: {erlaubt}")


def aus_tabelle(wert) -> str | None:
    """Der Status zu einem Zellinhalt, oder None wenn nichts dasteht.

    Eine leere Zelle heisst GEFUNDEN. Ein unbekannter Text wird nicht
    geraten - er kommt als None zurueck und der Aufrufer meldet ihn.
    """
    if wert is None or not str(wert).strip():
        return GEFUNDEN
    return _AUS_TEXT.get(str(wert).strip().casefold())


def text(status: str) -> str:
    return TEXT.get(status, status)


def ist_verfolgt(status: str) -> bool:
    """Wurde die Anzeige ueber das blosse Finden hinaus angefasst?

    Nur gefundene Anzeigen darf die Tabelle nach Ablauf der Frist
    vergessen. Sobald jemand etwas entschieden hat - auch "nicht
    interessant" - gehoert der Eintrag dauerhaft erhalten, sonst taucht
    dieselbe Anzeige beim naechsten Lauf wieder auf.
    """
    return status != GEFUNDEN
