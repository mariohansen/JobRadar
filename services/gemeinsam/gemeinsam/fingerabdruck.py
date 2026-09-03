"""Inhaltlicher Fingerabdruck einer Anzeige, quellenuebergreifend.

Dieselbe Stelle steht oft auf mehreren Portalen - bei der Bundesagentur,
auf Arbeitnow, im Karriereportal des Arbeitgebers. Jede Quelle vergibt
eine eigene Kennung, der Dedup ueber die Referenznummer greift also nur
innerhalb einer Quelle. Ohne einen zweiten, inhaltlichen Schluessel
stuende dieselbe Stelle drei- oder viermal in der Mail.

Verglichen werden Arbeitgeber, Titel und Ort - in normalisierter Form,
weil dieselbe Stelle je nach Portal anders geschrieben steht:

    "Data Engineer (m/w/d)"      vs. "Data Engineer (w/m/d)"
    "Beispiel GmbH & Co. KG"     vs. "Beispiel GmbH"
    "20095 Hamburg"              vs. "Hamburg, Deutschland"

Bewusst *nicht* normalisiert werden Erfahrungsstufen: "Senior Data
Engineer" und "Data Engineer" sind verschiedene Stellen und muessen
verschiedene Fingerabdruecke bekommen.

Der Abgleich ist eine Heuristik. Zwei wirklich verschiedene Stellen mit
gleichem Titel beim selben Arbeitgeber am selben Ort fallen zusammen -
das ist der akzeptierte Fehler, denn die Alternative waere, jede
Mehrfachlistung durchzulassen.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

# Geschlechtszusaetze in allen gaengigen Schreibweisen. Sie stehen mal in
# Klammern, mal mit Schraegstrich, mal ausgeschrieben.
GESCHLECHT = re.compile(
    r"[\(\[]?\s*(?:m\s*[/|]\s*w\s*[/|]\s*[dx]|w\s*[/|]\s*m\s*[/|]\s*[dx]"
    r"|d\s*[/|]\s*m\s*[/|]\s*w|m\s*[/|]\s*f\s*[/|]\s*[dx]|gn|all\s+genders?"
    r"|m\s*[/|]\s*w|w\s*[/|]\s*m|divers)\s*[\)\]]?",
    re.IGNORECASE,
)

# Rechtsformen und Firmierungszusaetze. "Beispiel GmbH & Co. KG" und
# "Beispiel GmbH" sind derselbe Arbeitgeber.
RECHTSFORM = re.compile(
    r"\b(?:gmbh|mbh|ag|se|kg|ohg|gbr|ug|e\.?\s*v|e\.?\s*k|co\.?\s*kg|co|"
    r"holding|group|deutschland|germany|international|inc|ltd|llc|plc|nv|bv)\b\.?",
    re.IGNORECASE,
)

# Postleitzahl vor dem Ortsnamen, und alles ab dem ersten Komma:
# "20095 Hamburg, Deutschland" -> "hamburg".
PLZ = re.compile(r"\b\d{4,5}\b")

NICHT_WORT = re.compile(r"[^\w\s]", re.UNICODE)
MEHRFACH_LEER = re.compile(r"\s+")

# Laenge des Hexadezimalausschnitts. 24 Zeichen sind 96 Bit - bei
# einigen tausend Anzeigen ist eine Kollision damit ausgeschlossen, und
# der Schluessel bleibt in Logausgaben noch lesbar.
LAENGE = 24

PRAEFIX = "fp#"


def _grundform(wert: Any) -> str:
    if not isinstance(wert, str):
        return ""
    text = GESCHLECHT.sub(" ", wert)
    text = NICHT_WORT.sub(" ", text)
    return MEHRFACH_LEER.sub(" ", text).strip().casefold()


def firma(wert: Any) -> str:
    """Arbeitgebername ohne Rechtsform und Firmierungszusaetze."""
    if not isinstance(wert, str):
        return ""
    ohne_form = RECHTSFORM.sub(" ", wert)
    return _grundform(ohne_form)


def titel(wert: Any) -> str:
    """Stellentitel ohne Geschlechtszusatz und Zeichensetzung."""
    return _grundform(wert)


def ort(wert: Any) -> str:
    """Ortsname ohne Postleitzahl, Land und Zusaetze hinter dem Komma."""
    if not isinstance(wert, str):
        return ""
    vorn = wert.split(",")[0]
    return _grundform(PLZ.sub(" ", vorn))


def _erster_ort(job: dict[str, Any]) -> str:
    for lokation in job.get("stellenlokationen") or []:
        adresse = lokation.get("adresse") or {}
        if isinstance(adresse.get("ort"), str) and adresse["ort"].strip():
            return adresse["ort"]
    return ""


def bestandteile(job: dict[str, Any]) -> tuple[str, str, str]:
    """Die drei normalisierten Teile - einzeln, damit sie pruefbar sind."""
    return (
        firma(job.get("firma")),
        titel(job.get("stellenangebotsTitel")),
        ort(_erster_ort(job)),
    )


def berechne(job: dict[str, Any]) -> str | None:
    """Fingerabdruck einer Anzeige, oder None wenn zu wenig dasteht.

    Ohne Arbeitgeber oder ohne Titel waere der Schluessel so grob, dass
    er fremde Stellen zusammenwerfen wuerde. Dann lieber kein
    inhaltlicher Abgleich - die Anzeige laeuft ueber die Referenznummer
    weiter und steht im Zweifel einmal zu viel in der Mail.
    """
    arbeitgeber, stelle, stadt = bestandteile(job)
    if not arbeitgeber or not stelle:
        return None

    roh = f"{arbeitgeber}|{stelle}|{stadt}".encode("utf-8")
    return hashlib.sha256(roh).hexdigest()[:LAENGE]


def schluessel(job: dict[str, Any]) -> str | None:
    """Fingerabdruck als DynamoDB-Schluessel, im eigenen Namensraum.

    Das Praefix trennt die Merkposten vom eigentlichen Bestand: ein
    Eintrag "fp#abc..." ist keine Anzeige, sondern die Notiz, dass es
    eine mit diesem Inhalt schon gibt.
    """
    wert = berechne(job)
    return f"{PRAEFIX}{wert}" if wert else None


def ist_merkposten(referenznummer: Any) -> bool:
    """Gehoert dieser Schluessel zum inhaltlichen Abgleich statt zu einer Anzeige?"""
    return isinstance(referenznummer, str) and referenznummer.startswith(PRAEFIX)
