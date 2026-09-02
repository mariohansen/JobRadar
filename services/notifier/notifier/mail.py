"""Aufbau der Benachrichtigungsmail.

Bewusst nuechtern gehalten: klarer Betreff ohne Ausrufezeichen oder
Grossbuchstaben, und immer ein reiner Textteil neben dem HTML-Teil.
Viele Spamfilter bewerten Nur-HTML-Mails schlechter, und der Textteil
ist ausserdem das, was in der Vorschau eines Mailprogramms erscheint.
"""
from __future__ import annotations

import html
from typing import Any


def betreff(anzeigen: list[dict[str, Any]]) -> str:
    anzahl = len(anzeigen)
    orte = {_ort(a) for a in anzeigen if _ort(a)}
    ortsangabe = orte.pop() if len(orte) == 1 else "Raum Hamburg"
    treffer = "neuer Treffer" if anzahl == 1 else "neue Treffer"
    return f"JobRadar: {anzahl} {treffer} ({ortsangabe})"


def _ort(job: dict[str, Any]) -> str:
    lokationen = job.get("stellenlokationen") or []
    if not lokationen:
        return ""
    return (lokationen[0].get("adresse") or {}).get("ort", "")


def _firma(job: dict[str, Any]) -> str:
    return job.get("firma") or "Arbeitgeber nicht genannt"


def _veroeffentlicht(job: dict[str, Any]) -> str:
    return job.get("datumErsteVeroeffentlichung") or "unbekannt"


def _stellenlink(job: dict[str, Any]) -> str:
    """Link in die Jobboerse.

    Die Oberflaeche der Bundesagentur erwartet die Referenznummer im
    Pfad; ueber diesen Weg ist die vollstaendige Anzeige samt Text
    erreichbar, den die Trefferliste der API nicht mitliefert.
    """
    referenz = job.get("referenznummer", "")
    return f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{referenz}"


def als_text(anzeigen: list[dict[str, Any]]) -> str:
    zeilen = [f"{len(anzeigen)} neue Stellenanzeigen:", ""]
    for job in anzeigen:
        zeilen += [
            job.get("stellenangebotsTitel", "ohne Titel"),
            f"  Arbeitgeber: {_firma(job)}",
            f"  Ort: {_ort(job) or 'nicht angegeben'}",
            f"  Veroeffentlicht: {_veroeffentlicht(job)}",
            f"  {_stellenlink(job)}",
            "",
        ]
    zeilen.append("Gesendet von JobRadar.")
    return "\n".join(zeilen)


def als_html(anzeigen: list[dict[str, Any]]) -> str:
    # html.escape auf jedem Feld: Stellentitel enthalten regelmaessig
    # kaufmaennische Und-Zeichen und Klammern, die sonst das Markup
    # zerlegen wuerden.
    eintraege = []
    for job in anzeigen:
        eintraege.append(
            "<li style=\"margin-bottom:14px\">"
            f"<a href=\"{html.escape(_stellenlink(job))}\">"
            f"<strong>{html.escape(job.get('stellenangebotsTitel', 'ohne Titel'))}</strong></a><br>"
            f"{html.escape(_firma(job))} &middot; {html.escape(_ort(job) or 'Ort nicht angegeben')}<br>"
            f"<span style=\"color:#666\">Veroeffentlicht: {html.escape(_veroeffentlicht(job))}</span>"
            "</li>"
        )
    return (
        "<html><body style=\"font-family:sans-serif;font-size:14px\">"
        f"<p>{len(anzeigen)} neue Stellenanzeigen:</p>"
        f"<ul style=\"padding-left:18px\">{''.join(eintraege)}</ul>"
        "<p style=\"color:#666\">Gesendet von JobRadar.</p>"
        "</body></html>"
    )
