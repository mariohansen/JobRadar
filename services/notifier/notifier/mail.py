"""Aufbau der Benachrichtigungsmail.

Bewusst nuechtern gehalten: klarer Betreff ohne Ausrufezeichen oder
Grossbuchstaben, und immer ein reiner Textteil neben dem HTML-Teil.
Viele Spamfilter bewerten Nur-HTML-Mails schlechter, und der Textteil
ist ausserdem das, was in der Vorschau eines Mailprogramms erscheint.

Was der filter-dedup unter `jobradar` angehaengt hat - Passung, Alter,
Entfernung - wird hier nur noch dargestellt. Fehlt es, faellt die Mail
auf ihre bisherige Form zurueck; dieser Dienst rechnet nichts aus und
braucht deshalb weder Profil noch Netzzugriff.
"""
from __future__ import annotations

import html
from typing import Any

# Muss zu filter_dedup.anreicherung.SCHLUESSEL passen.
ZUSATZ = "jobradar"

# Anzeigen ohne Bewertung sortieren hinter die bewerteten, statt mit
# einer erfundenen Null vorne zu stehen.
OHNE_BEWERTUNG = -1


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


def _zusatz(job: dict[str, Any]) -> dict[str, Any]:
    wert = job.get(ZUSATZ)
    return wert if isinstance(wert, dict) else {}


def punkte(job: dict[str, Any]) -> int:
    wert = _zusatz(job).get("punkte")
    return wert if isinstance(wert, int) else OHNE_BEWERTUNG


def sortiert(anzeigen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Beste Passung zuerst.

    Wer eine Mail mit zwoelf Treffern oeffnet, liest die ersten drei.
    Die sollen die sein, auf die es ankommt.
    """
    return sorted(anzeigen, key=punkte, reverse=True)


def _passungszeile(job: dict[str, Any]) -> str:
    """Stufe, Punktzahl und Treffer in einer Zeile, oder leer."""
    zusatz = _zusatz(job)
    stufe = zusatz.get("stufe")
    if not stufe:
        return ""

    teile = [str(stufe)]
    if isinstance(zusatz.get("punkte"), int):
        teile.append(f"{zusatz['punkte']} Punkte")

    treffer = zusatz.get("treffer") or []
    if treffer:
        teile.append("passt: " + ", ".join(treffer[:6]))
    luecken = zusatz.get("luecken") or []
    if luecken:
        teile.append("fehlt: " + ", ".join(luecken[:4]))

    return " | ".join(teile)


def _randdaten(job: dict[str, Any]) -> str:
    """Alter und Entfernung, soweit bekannt."""
    zusatz = _zusatz(job)
    teile = []

    alter = zusatz.get("alter_tage")
    if isinstance(alter, int):
        teile.append("heute veroeffentlicht" if alter == 0 else f"seit {alter} Tagen online")

    entfernung = zusatz.get("entfernung_km")
    if isinstance(entfernung, (int, float)):
        # Dezimalkomma: die Mail ist auf Deutsch, 8.2 km liest sich darin
        # wie ein Tippfehler.
        teile.append(f"{entfernung:g}".replace(".", ",") + " km")

    return " · ".join(teile)


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
    for job in sortiert(anzeigen):
        zeilen.append(job.get("stellenangebotsTitel", "ohne Titel"))

        bewertung = _passungszeile(job)
        if bewertung:
            zeilen.append(f"  {bewertung}")

        ort = _ort(job) or "nicht angegeben"
        rand = _randdaten(job)
        zeilen += [
            f"  Arbeitgeber: {_firma(job)}",
            f"  Ort: {ort}" + (f" ({rand})" if rand else ""),
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
    for job in sortiert(anzeigen):
        bewertung = _passungszeile(job)
        rand = _randdaten(job)

        # Die Stufe steht ueber dem Titel: sie entscheidet, ob der Rest
        # ueberhaupt gelesen wird.
        kopf = (
            f"<div style=\"color:#1f3864;font-weight:bold\">{html.escape(bewertung)}</div>"
            if bewertung
            else ""
        )
        fuss = f" &middot; {html.escape(rand)}" if rand else ""

        eintraege.append(
            "<li style=\"margin-bottom:14px\">"
            + kopf
            + f"<a href=\"{html.escape(_stellenlink(job))}\">"
            f"<strong>{html.escape(job.get('stellenangebotsTitel', 'ohne Titel'))}</strong></a><br>"
            f"{html.escape(_firma(job))} &middot; {html.escape(_ort(job) or 'Ort nicht angegeben')}<br>"
            f"<span style=\"color:#666\">Veroeffentlicht: {html.escape(_veroeffentlicht(job))}{fuss}</span>"
            "</li>"
        )
    return (
        "<html><body style=\"font-family:sans-serif;font-size:14px\">"
        f"<p>{len(anzeigen)} neue Stellenanzeigen:</p>"
        f"<ul style=\"padding-left:18px\">{''.join(eintraege)}</ul>"
        "<p style=\"color:#666\">Gesendet von JobRadar.</p>"
        "</body></html>"
    )
