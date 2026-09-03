"""Bewertung, wie gut eine Anzeige zum eigenen Profil passt.

Verglichen werden zwei Mengen von Begriffen: was die Anzeige verlangt
und was das Profil hergibt. Der Rest ist Arithmetik - kein Sprachmodell,
keine Kosten je Anzeige, und jede Bewertung laesst sich an den Spalten
"Treffer" und "Luecken" nachrechnen.

Die Punktzahl ist die gedaempfte Deckung: welcher Anteil dessen, was die
Anzeige verlangt, im Profil steht - mit einem Zuschlag im Nenner, der
duenne Anzeigen davon abhaelt, die Spitze zu belegen (siehe DAEMPFUNG).
Was im **Titel** steht, zaehlt dreifach: "Java Entwickler" sagt mehr
ueber die Stelle aus als eine Erwaehnung von Java im Fliesstext.

Ob ein Treffer einen eigenen Schwerpunkt betrifft, geht bewusst *nicht*
in die Zahl ein. Ein Bonus dafuer hat die Bewertung an der Spitze
unbrauchbar gemacht: zwei sehr verschiedene Anzeigen kamen beide auf
abgeschnittene 100. Die Unterscheidung steht deshalb dort, wo sie zu
sehen ist - Schwerpunkte tragen in der Trefferspalte einen Stern.

Die Schwellen sind gesetzt, nicht gemessen. Sie taugen als Startpunkt
und gehoeren nachjustiert, sobald genug bewertete Anzeigen vorliegen.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import faehigkeiten as fk

STUFE_A = "A – Volltreffer"
STUFE_B = "B – Naheliegend"
STUFE_C = "C – Randbereich"
# Sortiert hinter C, weil es kein Urteil ueber die Stelle ist, sondern
# ueber die Datenlage: ohne Anzeigentext gibt es nichts zu vergleichen.
STUFE_D = "D – zu wenig Angaben"

SCHWELLE_A = 55
SCHWELLE_B = 35

# Daempfung im Nenner. Ohne sie ist die Deckung ein reiner Anteil - und
# der belohnt wortkarge Anzeigen: eine, die vier Begriffe nennt und alle
# trifft, kaeme auf glatte 100 und stuende ueber einer, die zwoelf von
# fuenfzehn abdeckt. Genau verkehrt herum, denn die zweite sagt mehr
# ueber die Stelle und passt trotzdem.
#
# Mit dem Zuschlag muss eine Anzeige erst *Substanz* haben, um oben zu
# landen: vier von vier ergeben 44, sechs von acht 46, zwoelf von
# fuenfzehn 60. Der Wert ist gesetzt, nicht gemessen - `tracker
# rueckblick` stellt ihn gegen die tatsaechlichen Ausgaenge.
DAEMPFUNG = 5

# Unter so vielen erkannten Begriffen ist jede Prozentzahl Zufall: eine
# Anzeige, die nur "Java" nennt, ergaebe bei einem Treffer glatte 100.
MINDEST_BEGRIFFE = 3

TITELGEWICHT = 3

# Mehr passt in eine Tabellenzelle nicht sinnvoll hinein.
HOECHSTENS = 10


@dataclass(frozen=True)
class Bewertung:
    stufe: str
    punkte: int
    treffer: tuple[str, ...]
    luecken: tuple[str, ...]
    schwerpunkte: tuple[str, ...] = ()

    @property
    def treffertext(self) -> str:
        """Treffer, Schwerpunkte mit Stern."""
        markiert = tuple(
            f"{name}*" if name in self.schwerpunkte else name for name in self.treffer
        )
        return _gekuerzt(markiert)

    @property
    def lueckentext(self) -> str:
        return _gekuerzt(self.luecken)

    @property
    def brauchbar(self) -> bool:
        return self.stufe != STUFE_D


def _gekuerzt(begriffe: tuple[str, ...]) -> str:
    if len(begriffe) <= HOECHSTENS:
        return ", ".join(begriffe)
    rest = len(begriffe) - HOECHSTENS
    return ", ".join(begriffe[:HOECHSTENS]) + f" (+{rest})"


def _stufe(punkte: int) -> str:
    if punkte >= SCHWELLE_A:
        return STUFE_A
    if punkte >= SCHWELLE_B:
        return STUFE_B
    return STUFE_C


def bewerte(profil, titel: str, text: str = "") -> Bewertung:
    """Deckung zwischen den Anforderungen der Anzeige und dem Profil."""
    im_titel = set(fk.finde(titel))
    gefordert = fk.finde(f"{titel}\n{text}")

    eigene = profil.alle
    schwerpunkte = tuple(sorted(profil.kern))

    if len(gefordert) < MINDEST_BEGRIFFE:
        return Bewertung(
            STUFE_D, 0, tuple(sorted(im_titel & eigene)), (), schwerpunkte
        )

    moeglich = 0
    erreicht = 0
    treffer: list[str] = []
    luecken: list[str] = []

    for begriff in gefordert:
        gewicht = TITELGEWICHT if begriff in im_titel else 1
        moeglich += gewicht
        if begriff in eigene:
            erreicht += gewicht
            treffer.append(begriff)
        else:
            luecken.append(begriff)

    punkte = round(100 * erreicht / (moeglich + DAEMPFUNG))
    return Bewertung(
        _stufe(punkte), punkte, tuple(treffer), tuple(luecken), schwerpunkte
    )


def leer() -> Bewertung:
    """Bewertung ohne Profil - die Spalten bleiben dann leer."""
    return Bewertung("", 0, (), ())
