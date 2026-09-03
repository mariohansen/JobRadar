"""Der Skill-Trend als eine einzelne HTML-Datei.

Bewusst ohne Bibliotheken, ohne CDN und ohne Nachladen: die Datei steht
allein und laesst sich vom Dateisystem, aus einer Mail heraus oder ueber
einen S3-Link oeffnen. Die Balken sind schlichte Kaesten mit einer
prozentualen Breite; ein Diagrammpaket dafuer zu laden hiesse, sich fuer
ein Rechteck eine Abhaengigkeit einzuhandeln.

Zwei Ruecksichten, weil der Bericht auf dem Handy gelesen werden soll:
ein Ansichtsfenster-Meta und Umbrueche statt fester Breiten. Und ein
Farbschema, das der Systemeinstellung folgt - ein weisses Blatt um
Mitternacht ist niemandes Freund.
"""
from __future__ import annotations

import html
from datetime import datetime
from typing import Any

from gemeinsam import faehigkeiten as fk

STIL = """
:root {
  color-scheme: light dark;
  --grund: #ffffff; --schrift: #1a1a1a; --gedaempft: #5c5c5c;
  --linie: #e3e3e3; --kasten: #f7f7f8;
  --luecke: #b3261e; --staerke: #1f6f3f; --neutral: #1f3864;
}
@media (prefers-color-scheme: dark) {
  :root {
    --grund: #16181c; --schrift: #e9e9ea; --gedaempft: #a0a0a6;
    --linie: #2c2f36; --kasten: #1e2127;
    --luecke: #f2b8b5; --staerke: #7fd1a0; --neutral: #9db8f0;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 20px 16px 56px;
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--grund); color: var(--schrift);
  max-width: 820px; margin-inline: auto;
}
h1 { font-size: 1.45rem; margin: 0 0 4px; }
h2 { font-size: 1.1rem; margin: 34px 0 6px; }
p.hinweis { color: var(--gedaempft); margin: 0 0 18px; font-size: .9rem; }
.kennzahlen { display: flex; flex-wrap: wrap; gap: 10px; margin: 18px 0 6px; }
.kennzahl {
  flex: 1 1 130px; background: var(--kasten); border: 1px solid var(--linie);
  border-radius: 10px; padding: 10px 12px;
}
.kennzahl b { display: block; font-size: 1.5rem; line-height: 1.2; }
.kennzahl span { color: var(--gedaempft); font-size: .8rem; }
.zeile { margin: 7px 0; }
.kopfzeile {
  display: flex; justify-content: space-between; gap: 12px;
  font-size: .92rem; margin-bottom: 3px;
}
.kopfzeile em { color: var(--gedaempft); font-style: normal; white-space: nowrap; }
.balken { background: var(--kasten); border-radius: 5px; height: 9px; overflow: hidden; }
.balken > i { display: block; height: 100%; border-radius: 5px; }
.luecke > i { background: var(--luecke); }
.staerke > i { background: var(--staerke); }
.neutral > i { background: var(--neutral); }
table { border-collapse: collapse; width: 100%; font-size: .88rem; }
th, td { text-align: right; padding: 5px 7px; border-bottom: 1px solid var(--linie); }
th:first-child, td:first-child { text-align: left; }
th { color: var(--gedaempft); font-weight: 600; }
.rollbar { overflow-x: auto; }
footer {
  margin-top: 40px; padding-top: 14px; border-top: 1px solid var(--linie);
  color: var(--gedaempft); font-size: .82rem;
}
"""


def _e(wert: Any) -> str:
    return html.escape(str(wert))


def _balken(eintraege, klasse: str, hoechstwert: float) -> str:
    """Eine Liste aus Beschriftung, Zahl und Balken."""
    zeilen = []
    for begriff, anzahl, anteil in eintraege:
        breite = 100 * anteil / hoechstwert if hoechstwert else 0
        zeilen.append(
            f'<div class="zeile"><div class="kopfzeile"><span>{_e(begriff)}</span>'
            f"<em>{anzahl}&times; &middot; {anteil:.0%}</em></div>"
            f'<div class="balken {klasse}"><i style="width:{breite:.1f}%"></i></div></div>'
        )
    return "".join(zeilen)


def _hoechster_anteil(*listen) -> float:
    werte = [anteil for liste in listen for _, _, anteil in liste]
    return max(werte) if werte else 0.0


def _verlaufstabelle(auswertung, begriffe: list[str]) -> str:
    """Wie sich die gefragtesten Begriffe ueber die Monate entwickeln."""
    monate = auswertung.monate()
    if len(monate) < 2 or not begriffe:
        return (
            '<p class="hinweis">Fuer einen Verlauf braucht es mindestens '
            "zwei Monate im Archiv.</p>"
        )

    kopf = "".join(f"<th>{_e(m)}</th>" for m in monate)
    zeilen = []
    for begriff in begriffe:
        zellen = "".join(
            f"<td>{auswertung.verlauf[m].get(begriff, 0)}</td>" for m in monate
        )
        zeilen.append(f"<tr><td>{_e(begriff)}</td>{zellen}</tr>")

    return (
        '<div class="rollbar"><table><thead><tr><th>Begriff</th>'
        f"{kopf}</tr></thead><tbody>{''.join(zeilen)}</tbody></table></div>"
    )


def _kennzahl(wert: Any, beschriftung: str) -> str:
    return f'<div class="kennzahl"><b>{_e(wert)}</b><span>{_e(beschriftung)}</span></div>'


def _zeitraum(auswertung) -> str:
    if not auswertung.von or not auswertung.bis:
        return "kein Zeitraum"
    if auswertung.von == auswertung.bis:
        return f"{auswertung.von:%d.%m.%Y}"
    return f"{auswertung.von:%d.%m.%Y} bis {auswertung.bis:%d.%m.%Y}"


def baue(auswertung, profil: Any = None, titel: str = "JobRadar Skill-Trend") -> str:
    luecken = auswertung.wichtigste_luecken()
    staerken = auswertung.staerken()
    # Beide Listen an derselben Skala messen, sonst taeuscht der
    # Vergleich: ein voller Balken links und rechts hiesse sonst
    # Verschiedenes.
    massstab = _hoechster_anteil(luecken, staerken)

    kennzahlen = [_kennzahl(auswertung.anzeigen, "Anzeigen im Archiv")]
    if profil is not None:
        kennzahlen.append(_kennzahl(len(profil.alle), "Fähigkeiten im Profil"))
        volltreffer = next(
            (n for stufe, n in auswertung.stufen.items() if stufe.startswith("A")), 0
        )
        kennzahlen.append(_kennzahl(volltreffer, "davon Volltreffer"))
        if luecken:
            kennzahlen.append(_kennzahl(f"{luecken[0][2]:.0%}", f"verlangen {luecken[0][0]}"))

    teile = [
        f"<!doctype html><html lang=de><head><meta charset=utf-8>",
        '<meta name=viewport content="width=device-width, initial-scale=1">',
        f"<title>{_e(titel)}</title><style>{STIL}</style></head><body>",
        f"<h1>{_e(titel)}</h1>",
        f'<p class="hinweis">{_e(_zeitraum(auswertung))} &middot; '
        f"{auswertung.anzeigen} Anzeigen, jede einmal gezählt</p>",
        f'<div class="kennzahlen">{"".join(kennzahlen)}</div>',
    ]

    if not auswertung.aussagekraeftig():
        teile.append(
            '<p class="hinweis">Wenige Anzeigen im Bestand – die Anteile '
            "unten sind noch keine Aussage über den Markt.</p>"
        )

    if profil is None:
        teile += [
            "<h2>Am häufigsten verlangt</h2>",
            '<p class="hinweis">Ohne Profil lässt sich nicht sagen, was davon '
            "dir fehlt. Anlegen mit <code>python -m tracker.main profil</code>.</p>",
            _balken(
                [(b, n, auswertung.anteil(b)) for b, n in auswertung.nachfrage.most_common(20)],
                "neutral",
                _hoechster_anteil(
                    [(b, n, auswertung.anteil(b)) for b, n in auswertung.nachfrage.most_common(20)]
                ),
            ),
        ]
    else:
        teile += [
            "<h2>Was dir am häufigsten fehlt</h2>",
            '<p class="hinweis">Verlangt und nicht im Profil. Die oberste Zeile '
            "ist die Fähigkeit, mit der du am meisten Anzeigen gewinnst.</p>",
            _balken(luecken, "luecke", massstab)
            or '<p class="hinweis">Keine Lücken gefunden.</p>',
            "<h2>Was du abdeckst</h2>",
            '<p class="hinweis">Verlangt und im Profil vorhanden – dieselbe '
            "Skala wie oben.</p>",
            _balken(staerken, "staerke", massstab)
            or '<p class="hinweis">Noch keine Überschneidung gefunden.</p>',
        ]

    teile += [
        "<h2>Verlauf</h2>",
        '<p class="hinweis">Nennungen je Monat, für die zehn gefragtesten '
        "Begriffe. Der laufende Monat ist unvollständig.</p>",
        _verlaufstabelle(auswertung, [b for b, _ in auswertung.nachfrage.most_common(10)]),
    ]

    quellen = ", ".join(profil.quellen) if profil is not None and profil.quellen else "—"
    teile += [
        "<footer>",
        f"Erstellt am {datetime.now():%d.%m.%Y %H:%M} aus dem Rohdatenarchiv. ",
        f"Erkannt wird nur, was im Verzeichnis steht ({len(fk.KATALOG)} Begriffe); ",
        "was dort fehlt, taucht hier nicht auf. ",
        f"Profil aus: {_e(quellen)}.",
        "</footer></body></html>",
    ]
    return "".join(teile)
