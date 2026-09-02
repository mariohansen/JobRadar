"""Bewertung, ob eine Anzeige weitergereicht wird.

Der Poller sucht bereits nach Stellenbezeichnungen. Hier faellt heraus,
was formal passt, aber inhaltlich nicht - vor allem Praktika und
Werkstudentenstellen, die unter denselben Berufsbegriffen gefuehrt
werden.
"""
from __future__ import annotations

import re
from typing import Any


def durchsuchbarer_text(job: dict[str, Any]) -> str:
    """Alle Felder, in denen ein Ausschlussbegriff stehen kann."""
    teile = [
        job.get("stellenangebotsTitel") or "",
        job.get("hauptberuf") or "",
        *(job.get("alleBerufe") or []),
    ]
    return " ".join(teile).lower()


def enthaelt(text: str, begriff: str) -> bool:
    """Kommt der Begriff am Anfang eines Wortes vor?

    Reine Teilzeichenketten waeren bei kurzen Begriffen gefaehrlich:
    "sr" steckt auch in "Israel". Nur auf den Wortanfang zu pruefen
    loest das, ohne die laengeren Begriffe zu schwaechen - "praktikum"
    erfasst weiterhin auch "Praktikumsstelle", weil das Wortende offen
    bleibt.
    """
    return re.search(r"\b" + re.escape(begriff), text) is not None


def passt(
    job: dict[str, Any], ausschluss: tuple[str, ...], pflicht: tuple[str, ...]
) -> bool:
    text = durchsuchbarer_text(job)

    if any(enthaelt(text, begriff) for begriff in ausschluss):
        return False

    # Leere Pflichtliste bedeutet: keine Einschraenkung.
    if pflicht and not any(enthaelt(text, begriff) for begriff in pflicht):
        return False

    return True
