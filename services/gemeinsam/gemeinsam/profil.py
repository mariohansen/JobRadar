"""Faehigkeitsprofil aus den eigenen Bewerbungsunterlagen.

Liest Lebenslauf und Zeugnisse, sucht die Begriffe aus dem Verzeichnis
darin und legt das Ergebnis als bearbeitbare Datei ab. Bearbeitbar ist
der Punkt: eine Mustersuche findet, was dasteht, und ein Lebenslauf
erwaehnt manches nur beilaeufig, was in Wahrheit im Zentrum steht - und
umgekehrt. Die Datei hat deshalb zwei Listen fuer Nachbesserungen von
Hand.

Nichts davon verlaesst den Rechner. Der Text der Unterlagen wird nur
gelesen, nie gespeichert und nie ausgegeben; abgelegt werden allein die
erkannten Begriffe. Die Datei gehoert - wie die Unterlagen selbst -
nicht ins Repo, siehe .gitignore.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import faehigkeiten as fk

log = logging.getLogger(__name__)


def wurzel() -> Path:
    """Wurzelverzeichnis des Projekts.

    Die Tracker-Befehle werden aus services/tracker aufgerufen, die
    Unterlagen liegen aber daneben im Projektordner. Ein relativer
    Vorgabepfad haenge damit davon ab, wo man gerade steht - und legte
    beim ersten Fehlgriff ein zweites, leeres bewerbung/ an.
    """
    return Path(__file__).resolve().parents[3]


VORGABE_UNTERLAGEN = wurzel() / "bewerbung"


def vorgabe_pfad() -> Path:
    """Ablageort des Profils.

    Auf der Instanz gibt es kein Projektverzeichnis - dort legt das
    Ausrollskript die Datei ab und nennt den Ort in JOBRADAR_PROFIL.
    """
    aus_umgebung = os.environ.get("JOBRADAR_PROFIL", "").strip()
    return Path(aus_umgebung) if aus_umgebung else VORGABE_UNTERLAGEN / "profil.json"

# Ab wie vielen Nennungen ein Begriff als Schwerpunkt gilt. Ein
# Lebenslauf nennt seine Kernthemen mehrfach - im Werdegang, in den
# Projekten und noch einmal in der Kenntnisliste.
KERN_SCHWELLE = 3

HINWEIS = (
    "Von Hand bearbeitbar. 'eigene' ergaenzt Faehigkeiten, die in den "
    "Unterlagen fehlen oder nur beilaeufig vorkommen, 'ausgeschlossen' "
    "streicht falsch erkannte. Beide zaehlen als Schwerpunkt. Gueltige "
    "Bezeichnungen stehen in tracker/faehigkeiten.py."
)


class ProfilFehler(RuntimeError):
    """Das Profil liegt nicht vor oder ist unbrauchbar."""


@dataclass(frozen=True)
class Profil:
    faehigkeiten: dict[str, int]
    eigene: tuple[str, ...] = ()
    ausgeschlossen: tuple[str, ...] = ()
    quellen: tuple[str, ...] = ()

    @property
    def alle(self) -> set[str]:
        aus_unterlagen = set(self.faehigkeiten) | set(self.eigene)
        return aus_unterlagen - set(self.ausgeschlossen)

    @property
    def kern(self) -> set[str]:
        """Schwerpunkte: mehrfach genannt oder von Hand eingetragen.

        Wer einen Begriff selbst nachtraegt, meint ihn - deshalb wiegt
        eine eigene Eintragung so schwer wie eine mehrfache Nennung.
        """
        haeufig = {n for n, anzahl in self.faehigkeiten.items() if anzahl >= KERN_SCHWELLE}
        return (haeufig | set(self.eigene)) - set(self.ausgeschlossen)


def text_aus_pdf(pfad: Path) -> str:
    """Textebene eines PDF, oder leer bei einem reinen Scan.

    Eingescannte Zeugnisse enthalten nur Bilder. Ohne Texterkennung ist
    daraus nichts zu holen; das meldet der Aufrufer, statt es stumm zu
    uebergehen.
    """
    from pypdf import PdfReader

    try:
        seiten = PdfReader(pfad).pages
    except Exception as exc:  # pypdf wirft je nach Defekt Verschiedenes
        log.warning("%s laesst sich nicht lesen: %s", pfad.name, exc)
        return ""
    return "\n".join((seite.extract_text() or "") for seite in seiten)


def _text_aus_datei(pfad: Path) -> str:
    if pfad.suffix.lower() == ".pdf":
        return text_aus_pdf(pfad)
    return pfad.read_text(encoding="utf-8", errors="replace")


def erstelle(verzeichnis: Path) -> tuple[Profil, list[str]]:
    """Profil aus allen Unterlagen eines Verzeichnisses.

    Gibt zusaetzlich die Dateien zurueck, aus denen sich kein Text
    gewinnen liess - meist Scans.
    """
    dateien = sorted(
        p for p in verzeichnis.iterdir()
        if p.is_file() and p.suffix.lower() in (".pdf", ".txt", ".md")
    )
    if not dateien:
        raise ProfilFehler(f"In {verzeichnis} liegen keine Unterlagen (.pdf, .txt, .md)")

    gesamt: dict[str, int] = {}
    gelesen: list[str] = []
    stumm: list[str] = []

    for pfad in dateien:
        text = _text_aus_datei(pfad)
        if len(text.strip()) < 200:
            stumm.append(pfad.name)
            continue
        gelesen.append(pfad.name)
        for name, anzahl in fk.haeufigkeiten(text).items():
            gesamt[name] = gesamt.get(name, 0) + anzahl

    if not gelesen:
        raise ProfilFehler(
            "Aus keiner Unterlage liess sich Text gewinnen. "
            "Eingescannte Dokumente enthalten keine Textebene."
        )

    return Profil(faehigkeiten=gesamt, quellen=tuple(gelesen)), stumm


def speichere(profil: Profil, pfad: Path) -> None:
    """Schreibt das Profil, ohne bereits gepflegte Listen zu verlieren."""
    pfad.parent.mkdir(parents=True, exist_ok=True)
    inhalt = {
        "hinweis": HINWEIS,
        "erstellt_am": date.today().isoformat(),
        "quellen": list(profil.quellen),
        # Absteigend sortiert - die Schwerpunkte stehen dann oben und die
        # Datei laesst sich von Hand ueberfliegen.
        "faehigkeiten": dict(
            sorted(profil.faehigkeiten.items(), key=lambda p: (-p[1], p[0]))
        ),
        "eigene": list(profil.eigene),
        "ausgeschlossen": list(profil.ausgeschlossen),
    }
    pfad.write_text(
        json.dumps(inhalt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def lade(pfad: Path) -> Profil:
    if not pfad.exists():
        raise ProfilFehler(
            f"{pfad} gibt es nicht. Anlegen mit:\n"
            f"  python -m tracker.main profil"
        )
    try:
        inhalt = json.loads(pfad.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProfilFehler(f"{pfad} ist kein gueltiges JSON: {exc}") from exc

    profil = Profil(
        faehigkeiten={str(k): int(v) for k, v in (inhalt.get("faehigkeiten") or {}).items()},
        eigene=tuple(inhalt.get("eigene") or ()),
        ausgeschlossen=tuple(inhalt.get("ausgeschlossen") or ()),
        quellen=tuple(inhalt.get("quellen") or ()),
    )

    # Ein Tippfehler in einer von Hand gepflegten Liste wuerde sonst
    # stumm wirkungslos bleiben.
    unbekannt = sorted(
        (set(profil.eigene) | set(profil.ausgeschlossen)) - set(fk.KATEGORIE_VON)
    )
    if unbekannt:
        log.warning(
            "Unbekannte Bezeichnungen in %s: %s. Gueltige stehen in faehigkeiten.py",
            pfad.name,
            ", ".join(unbekannt),
        )

    return profil
