"""Wie viel Homeoffice eine Stelle zulaesst.

Die Schnittstelle kennt drei Felder: `homeofficeprozent` als Zahl,
`homeofficetyp` mit NACH_VEREINBARUNG oder ANGABE_IN_PROZENT, und
`homeofficemoeglich` als Ja/Nein. Gepflegt sind sie selten - bei den
beobachteten Anzeigen steht fast ueberall gar nichts.

Im Anzeigentext steht dagegen regelmaessig etwas, und zwar genauer:

    "100 % Homeoffice innerhalb Deutschlands"
    "ein hybrides Arbeitsmodell"
    "Mobiles Arbeiten nach Absprache"
    "Ortsunabhaengig: Homeoffice oder an einem unserer Standorte"

Deshalb wird beides gelesen, in dieser Rangfolge: eine Prozentzahl der
Schnittstelle schlaegt alles, danach kommt der Text, und erst zuletzt
die schwachen Ja/Nein-Felder.

Der wichtigste Unterschied zur frueheren Fassung: **fehlt jede Angabe,
steht die Zelle leer.** Vorher stand dort "vor Ort" - eine Behauptung,
die die Daten nicht hergeben, und der haeufigste Grund fuer falsche
Werte in der Spalte. "vor Ort" gibt es jetzt nur, wenn die Anzeige es
sagt.

`NACH_VEREINBARUNG` gilt weiterhin nicht als remote (ADR 0006): der Wert
sagt nur, dass darueber zu reden ist.
"""
from __future__ import annotations

import re
from typing import Any

# Ausdruecklich kein Homeoffice. Steht selten da, ist dann aber eindeutig.
# "vor Ort" allein reicht nicht - das steht auch in "Sportangebote direkt
# vor Ort" und "Termine beim Kunden vor Ort".
NUR_VOR_ORT = re.compile(
    r"kein(?:e|erlei)?\s+(?:m(?:ö|oe)glichkeit\s+(?:zu|auf|zum)\s+)?home[-\s]?office"
    r"|100\s*%\s*pr(?:ä|ae)senz"
    r"|ausschlie(?:ß|ss)lich\s+vor\s+ort"
    r"|pr(?:ä|ae)senzpflicht",
    re.IGNORECASE,
)

# Vollstaendig entfernt, in allen beobachteten Schreibweisen.
VOLLSTAENDIG = re.compile(
    r"100\s*%?\s*(?:ig\w*\s+)?(?:remote|home[-\s]?office)"
    r"|(?:remote|home[-\s]?office)[^.\n]{0,20}\bzu\s*100\s*%"
    r"|zu\s*100\s*%\s*(?:\w+\s+){0,2}home[-\s]?office"
    r"|(?:vollst(?:ä|ae)ndig|komplett|dauerhaft|fully)\s+remote"
    r"|remote[-\s]?first"
    r"|ortsunabh(?:ä|ae)ngig",
    re.IGNORECASE,
)

# Konkreter Umfang in Tagen je Woche.
TAGE = re.compile(
    r"(\d)\s*(?:bis\s*\d\s*)?tage?n?\s*(?:pro\s*woche\s*)?"
    r"(?:im\s+|in\s+der\s+|)(?:home[-\s]?office|remote|mobiles?\s+arbeiten)"
    r"|(?:home[-\s]?office|remote)[^.\n]{0,15}?(\d)\s*tage?n?\s*(?:pro\s*woche)?",
    re.IGNORECASE,
)

# Hybrid nur im Zusammenhang mit Arbeit - "hybride Cloud" ist etwas
# anderes.
HYBRID = re.compile(r"hybrid\w*\s+(?:arbeit|modell)", re.IGNORECASE)

# Moeglich, aber ohne Umfang.
MOEGLICH = re.compile(
    r"mobiles?\s+arbeiten"
    r"|home[-\s]?office[-\s]?option"
    r"|home[-\s]?office\s*\((?:teilweise|anteilig)\)"
    r"|m(?:ö|oe)glichkeit[^.\n]{0,25}home[-\s]?office"
    r"|home[-\s]?office[^.\n]{0,15}m(?:ö|oe)glich"
    r"|m(?:ö|oe)glichkeit[^.\n]{0,25}remote\s+zu\s+arbeiten"
    r"|teilweise\s+home[-\s]?office",
    re.IGNORECASE,
)


def _text(wert: Any) -> str:
    return wert.strip() if isinstance(wert, str) else ""


def aus_prozent(prozent: Any) -> str:
    """Die belastbarste Angabe: eine Zahl der Schnittstelle."""
    if not isinstance(prozent, (int, float)):
        return ""
    if prozent >= 100:
        return "100 % remote"
    if prozent > 0:
        return f"hybrid, {int(prozent)} % Homeoffice"
    return ""


def aus_text(text: str) -> str:
    """Was der Anzeigentext ueber das Arbeitsmodell sagt, oder leer."""
    if not text:
        return ""

    if NUR_VOR_ORT.search(text):
        return "vor Ort"
    if VOLLSTAENDIG.search(text):
        return "100 % remote"

    treffer = TAGE.search(text)
    if treffer:
        tage = next((g for g in treffer.groups() if g), None)
        # Fuenf Tage und mehr sind keine Teilzeitregelung mehr.
        if tage and 1 <= int(tage) <= 4:
            wort = "Tag" if tage == "1" else "Tage"
            return f"hybrid, {tage} {wort}/Woche"
        if tage:
            return "100 % remote"

    if HYBRID.search(text):
        return "hybrid, Umfang offen"
    if MOEGLICH.search(text):
        return "möglich, Umfang offen"
    return ""


def bestimme(roh: dict[str, Any], detail: dict[str, Any], text: str = "") -> str:
    """Das Arbeitsmodell aus allem, was vorliegt.

    Rangfolge: Prozentzahl der Schnittstelle, dann der Anzeigentext, dann
    die schwachen Ja/Nein-Felder. Ohne jede Angabe bleibt die Zelle leer -
    lieber nichts sagen als "vor Ort" behaupten.
    """
    roh = roh or {}
    detail = detail or {}

    aus_zahl = aus_prozent(roh.get("homeofficeprozent"))
    if aus_zahl:
        return aus_zahl

    gefunden = aus_text(text)
    if gefunden:
        return gefunden

    typ = _text(roh.get("homeofficetyp")) or _text(detail.get("homeofficetyp"))
    if typ.upper() == "NACH_VEREINBARUNG":
        return "nach Vereinbarung"
    if roh.get("homeofficemoeglich") or detail.get("homeofficemoeglich"):
        return "möglich, Umfang offen"
    return ""
