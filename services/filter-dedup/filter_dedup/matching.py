"""Bewertung, ob eine Anzeige weitergereicht wird.

Der Poller sucht bereits nach Stellenbezeichnungen. Hier faellt heraus,
was formal passt, aber inhaltlich nicht - vor allem Praktika und
Werkstudentenstellen, die unter denselben Berufsbegriffen gefuehrt
werden.

Die Ausschlussbegriffe und die Wortanfang-Pruefung liegen in
`gemeinsam.ausschluss`, damit der `tracker` dieselbe Liste anwenden
kann - was in die Mail kommt, soll auch in die Tabelle kommen.
"""
from __future__ import annotations

from typing import Any

from gemeinsam.ausschluss import arbeitgeber_grund, enthaelt, grund


def durchsuchbarer_text(job: dict[str, Any]) -> str:
    """Alle Felder, in denen ein Ausschlussbegriff stehen kann."""
    teile = [
        job.get("stellenangebotsTitel") or "",
        job.get("hauptberuf") or "",
        *(job.get("alleBerufe") or []),
    ]
    return " ".join(teile).lower()


def passt(
    job: dict[str, Any],
    ausschluss: tuple[str, ...],
    pflicht: tuple[str, ...],
    arbeitgeber: tuple[str, ...] = (),
) -> bool:
    if arbeitgeber_grund(job.get("firma"), arbeitgeber):
        return False

    text = durchsuchbarer_text(job)

    if grund(text, ausschluss):
        return False

    # Leere Pflichtliste bedeutet: keine Einschraenkung.
    if pflicht and not any(enthaelt(text, begriff) for begriff in pflicht):
        return False

    return True
