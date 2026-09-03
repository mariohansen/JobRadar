# ADR 0011: Homeoffice aus dem Anzeigentext, und leer statt „vor Ort"

Datum: 2026-09-04
Status: akzeptiert

## Kontext

Die Spalte `Homeoffice-Modell` stimmte oft nicht. Sie las drei Felder der
Schnittstelle — `homeofficeprozent`, `homeofficetyp`,
`homeofficemoeglich` — und schrieb `vor Ort`, wenn keines davon etwas
sagte.

Gepflegt sind diese Felder aber selten. Ergebnis: von 329 Anzeigen
standen **223 auf `vor Ort`**, darunter reihenweise solche, deren Text
ausdrücklich etwas anderes sagte:

```
"100 % Homeoffice innerhalb Deutschlands"
"ein hybrides Arbeitsmodell"
"Ortsunabhängig: Homeoffice oder an einem unserer Standorte"
"Mobiles Arbeiten nach Absprache"
```

Zwei getrennte Fehler steckten darin: der Text wurde nicht gelesen, und
das Fehlen einer Angabe wurde als Aussage gewertet.

## Entscheidung

**Der Anzeigentext wird gelesen.** `gemeinsam/homeoffice.py` erkennt
vollständige Remote-Arbeit, einen Umfang in Tagen je Woche, hybride
Modelle und unbestimmte Möglichkeiten — jeweils in den Schreibweisen,
die in echten Anzeigen vorkommen.

**Rangfolge:** eine Prozentzahl der Schnittstelle schlägt alles (sie ist
die einzige harte Zahl, ADR 0006), danach kommt der Text, zuletzt die
schwachen Ja/Nein-Felder. Der Text ist genauer als
`homeofficemoeglich`, aber unschärfer als eine Zahl.

**Ohne jede Angabe bleibt die Zelle leer.** Das ist der eigentliche
Punkt. `vor Ort` gibt es nur noch, wenn die Anzeige es sagt —
„keine Möglichkeit zum Homeoffice", „Präsenzpflicht". Eine leere Zelle
heißt: wir wissen es nicht. Das ist unbequemer zu lesen und ehrlicher.

An 197 Anzeigen gemessen:

| Wert | vorher | nachher |
|------|--------|---------|
| `vor Ort` | 223 | 1 |
| `100 % remote` | 12 | 30 |
| `nach Vereinbarung` | 83 | 28 |
| `hybrid` (alle Formen) | 11 | 28 |
| `möglich, Umfang offen` | 0 | 22 |
| *(leer)* | 0 | 87 |

Die 87 leeren Zellen sind kein Rückschritt: dort stand vorher eine
erfundene Angabe.

## Ein beiläufiges „vor Ort" zählt nicht

Der naheliegende Ansatz — im Text nach „vor Ort" suchen — geht schief.
Die Wendung steht in ganz anderem Zusammenhang:

```
"Sportangebote direkt vor Ort, um Körper und Kopf in Balance zu halten"
"Du nimmst gelegentliche Abstimmungstermine bei unseren Kunden vor Ort wahr"
```

Deshalb wird `vor Ort` nur aus ausdrücklichen Verneinungen abgeleitet,
nie aus der bloßen Erwähnung. Dasselbe gilt für „hybrid": gesucht wird
`hybrid… arbeit|modell`, sonst fiele jede hybride Cloud-Architektur mit
hinein.

## Konsequenzen

Der Poller filtert im bundesweiten Durchgang weiterhin **nur** über
`homeofficeprozent` (ADR 0006). Diese Entscheidung betrifft die
Darstellung in der Tabelle, nicht die Suche: eine Textformulierung ist
gut genug, um sie in einer Spalte zu zeigen, aber nicht, um darauf eine
bundesweite Suche zu gründen.

Die Erkennung ist eine Mustersuche wie die für Benefits und Kontakt, mit
demselben Preis: was anders formuliert ist, wird nicht gefunden. Sie
liegt deshalb in einer Spalte, die der Export überschreibt — nicht in
einer, an der eine Entscheidung hängt.
