"""Gemeinsames Handwerkszeug der Stellenquellen.

Jede Quelle liefert ihr eigenes Format. Damit die nachgelagerte Pipeline
nicht fuer jede eine Sonderbehandlung braucht, uebersetzt jede Quelle ihr
Ergebnis in *ein* Format - und zwar in das der Jobsuche-API der
Bundesagentur, weil das schon ueberall gelesen wird: im filter-dedup, in
der Anreicherung, im Tracker-Export.

Das ist eine bewusste Entscheidung gegen ein neutrales eigenes Schema.
Ein solches waere sauberer, haette aber jeden Leser weiter unten
gleichzeitig aendern muessen. So aendert sich flussabwaerts nichts, und
neue Quellen sind je eine Datei.

Zwei Felder kommen hinzu:

* `quelle` - woher die Anzeige stammt. Nur so laesst sich spaeter
  entscheiden, ob ein Anzeigentext nachgeladen werden muss (bei der
  Bundesagentur ja, bei den uebrigen liegt er schon bei).
* `referenznummer` traegt die Quelle als Praefix. Zwei Portale koennten
  sonst dieselbe Kennung vergeben.
"""
from __future__ import annotations

import html
import json
import logging
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from typing import Any, Iterable

from gemeinsam import faehigkeiten as fk

log = logging.getLogger(__name__)

TIMEOUT_SEKUNDEN = 25

# Pause zwischen zwei Seitenabrufen derselben Quelle. Diese Boersen
# stellen ihre Schnittstelle kostenlos und ohne Vertrag bereit; ein Lauf
# soll nicht wie ein Lasttest aussehen. Dieselbe Zurueckhaltung, aus der
# auch der Poller nur alle zehn Stunden laeuft.
PAUSE_SEKUNDEN = 1.0

# Ein sprechender Name statt des urllib-Vorgabewerts. Wer in seinen Logs
# sieht, wer da anfragt, kann sich melden, statt einfach zu sperren.
BENUTZERKENNUNG = "JobRadar/1.0 (persoenliche Stellensuche; +https://github.com/)"

SKRIPT_UND_STIL = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
ABSATZENDE = re.compile(r"</(p|div|li|tr|h[1-6])\s*>|<br\s*/?>", re.IGNORECASE)
TAG = re.compile(r"<[^>]+>")
MEHRFACH_LEERZEILE = re.compile(r"\n{3,}")


class QuellenFehler(RuntimeError):
    """Eine Stellenquelle war nicht erreichbar oder antwortete unerwartet."""


class ZuVieleAnfragen(QuellenFehler):
    """Die Quelle bremst uns aus (HTTP 429).

    Kein Grund, den Lauf abzubrechen: was bis hierher eingesammelt wurde,
    ist brauchbar, und der naechste Lauf kommt in zehn Stunden. Die
    seitenweise lesenden Quellen fangen das ab und hoeren einfach auf.
    """


def hole_json(url: str, kopfzeilen: dict[str, str] | None = None) -> Any:
    anfrage = urllib.request.Request(
        url, headers={"User-Agent": BENUTZERKENNUNG, "Accept": "application/json", **(kopfzeilen or {})}
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=TIMEOUT_SEKUNDEN) as antwort:
            return json.load(antwort)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise ZuVieleAnfragen(f"HTTP 429 von {url}") from exc
        raise QuellenFehler(f"HTTP {exc.code} von {url}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise QuellenFehler(f"Keine Antwort von {url}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise QuellenFehler(f"Antwort von {url} ist kein JSON: {exc}") from exc


def pause() -> None:
    """Kurz warten, bevor die naechste Seite derselben Quelle drankommt."""
    time.sleep(PAUSE_SEKUNDEN)


def text_aus_html(roh: Any) -> str:
    """Fliesstext aus einer HTML-Beschreibung.

    Die Begriffssuche laeuft ueber regulaere Ausdruecke mit Wortgrenzen.
    Bliebe das Markup stehen, klebten Woerter an Tags ("</b>Java") und
    Aufzaehlungen liefen ohne Trennung ineinander.
    """
    if not isinstance(roh, str) or not roh.strip():
        return ""
    ohne_skript = SKRIPT_UND_STIL.sub(" ", roh)
    mit_umbruch = ABSATZENDE.sub("\n", ohne_skript)
    nur_text = TAG.sub(" ", mit_umbruch)
    entschluesselt = html.unescape(nur_text)
    zeilen = [" ".join(zeile.split()) for zeile in entschluesselt.split("\n")]
    return MEHRFACH_LEERZEILE.sub("\n\n", "\n".join(z for z in zeilen if z)).strip()


def als_datum(wert: Any) -> str:
    """Veroeffentlichungsdatum als YYYY-MM-DD, aus Zeitstempel oder ISO-Text."""
    if isinstance(wert, (int, float)) and wert > 0:
        return datetime.fromtimestamp(float(wert), tz=timezone.utc).strftime("%Y-%m-%d")
    if isinstance(wert, str) and wert.strip():
        roh = wert.strip()
        if roh.isdigit():
            return als_datum(int(roh))
        try:
            return datetime.fromisoformat(roh.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            # Manche Portale liefern nur das Datum, andere RFC-2822.
            for muster in ("%Y-%m-%d", "%d.%m.%Y", "%a, %d %b %Y %H:%M:%S %z"):
                try:
                    return datetime.strptime(roh, muster).date().isoformat()
                except ValueError:
                    continue
    return ""


PLZ_UND_ORT = re.compile(r"^\s*(\d{4,5})\s+(.*\S)\s*$")


def lokationen(orte: Iterable[Any]) -> list[dict[str, Any]]:
    """Ortsangaben in die Struktur der Jobsuche-API.

    Die anderen Portale liefern eine Zeichenkette wie "20095 Hamburg"
    oder "Hamburg, Deutschland"; die Bundesagentur eine verschachtelte
    Adresse. Hier entsteht die verschachtelte Form.
    """
    gebaut: list[dict[str, Any]] = []
    for eintrag in orte:
        if not isinstance(eintrag, str) or not eintrag.strip():
            continue
        vorn = eintrag.split(",")[0].strip()
        treffer = PLZ_UND_ORT.match(vorn)
        plz, ort = (treffer.group(1), treffer.group(2)) if treffer else ("", vorn)
        if ort:
            gebaut.append({"adresse": {"plz": plz, "ort": ort}})
    return gebaut


def passt_zum_begriff(titel: str, begriffe: Iterable[str]) -> bool:
    """Trifft mindestens ein Suchbegriff auf den Titel zu?

    Die meisten Portale kennen keine Feldsuche, ihre Trefferliste ist
    einfach der ganze Bestand. Gefiltert wird deshalb hier, auf zwei Wegen:

    Nennt der Begriff genau eine Faehigkeit aus dem Verzeichnis, gilt
    deren geprueftes Muster. Das ist bei kurzen Namen entscheidend:
    "Java" darf nicht ueber die Teilzeichenkette in "JavaScript"
    anschlagen, denn das ist eine andere Sprache.

    Sonst muessen alle Woerter des Begriffs als Teilzeichenkette
    vorkommen. Auf Teilzeichenketten und nicht auf Wortgrenzen, weil
    deutsche Stellentitel zusammenschreiben: "entwickler" soll auch
    "Softwareentwickler" finden und "Data Engineer" auch
    "Data Platform Engineer" - aber keinen Vertriebsposten.
    """
    gesenkt = (titel or "").casefold()
    if not gesenkt:
        return False

    for begriff in begriffe:
        muster = fk.muster_fuer(begriff)
        if muster is not None:
            if muster.search(gesenkt):
                return True
            continue

        woerter = [w for w in re.split(r"\W+", begriff.casefold()) if w]
        if woerter and all(w in gesenkt for w in woerter):
            return True
    return False


def im_zeitfenster(datum: str, tage: int) -> bool:
    """Liegt das Veroeffentlichungsdatum innerhalb der letzten N Tage?

    Ein leeres Datum gilt als innerhalb: lieber eine Anzeige zu viel als
    eine verpasste, der Dedup faengt Wiederholungen ohnehin ab.
    """
    if not datum or tage <= 0:
        return True
    try:
        veroeffentlicht = date.fromisoformat(datum)
    except ValueError:
        return True
    return (date.today() - veroeffentlicht).days <= tage


def anzeige(
    quelle: str,
    kennung: str,
    titel: str,
    firma: str,
    orte: Iterable[Any] = (),
    beschreibung: str = "",
    veroeffentlicht: Any = None,
    url: str = "",
    berufe: Iterable[str] = (),
    homeofficeprozent: int | None = None,
) -> dict[str, Any] | None:
    """Eine Anzeige im Format der Jobsuche-API, oder None wenn unbrauchbar.

    Ohne Titel oder Kennung laesst sich weder deduplizieren noch etwas
    anzeigen - so ein Datensatz wird verworfen statt halb weitergereicht.
    """
    titel = (titel or "").strip()
    kennung = str(kennung or "").strip()
    if not titel or not kennung:
        return None

    berufsliste = [b.strip() for b in berufe if isinstance(b, str) and b.strip()]
    gebaut: dict[str, Any] = {
        "referenznummer": f"{quelle}:{kennung}",
        "quelle": quelle,
        "stellenangebotsTitel": titel,
        "firma": (firma or "").strip(),
        "stellenlokationen": lokationen(orte),
        "datumErsteVeroeffentlichung": als_datum(veroeffentlicht),
        "hauptberuf": berufsliste[0] if berufsliste else "",
        "alleBerufe": berufsliste,
        # Der Text liegt bei diesen Quellen schon in der Trefferliste.
        # Der Anreicherungsschritt muss ihn deshalb nicht nachladen.
        "stellenangebotsBeschreibung": beschreibung,
        "externeURL": (url or "").strip(),
    }
    if homeofficeprozent is not None:
        gebaut["homeofficeprozent"] = homeofficeprozent
    return gebaut
