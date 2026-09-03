# ADR 0010: Gedämpfte Passung, und die Tabelle als Eingabefeld

Datum: 2026-09-03
Status: akzeptiert

## Kontext

Zwei Beobachtungen am laufenden Bestand.

**Die Bewertung stellte das Falsche nach oben.** Die Punktzahl war die
reine Deckung, `erreicht / möglich`. Damit gewann, wer wenig sagte:

| Punkte | Anzeige | Treffer | Lücken |
|---|---|---|---|
| **100** | Fachinformatiker, Data Engineer | SQL, Linux, Agile, Deutsch | – |
| **75** | Senior Data Engineer (w/m/d) | CI/CD, Git, Monitoring, DevOps, Deutsch, Englisch | ETL, Data Warehouse |

Vier von vier schlug sechs von acht. Genau verkehrt herum: die zweite
Anzeige sagt mehr über die Stelle und passt trotzdem weitgehend.

**Die Handspalten blieben leer.** `Datum Abgabe`, `Frist Rückmeldung`,
`Datum Rückmeldung`, `Notizen` — in 329 Zeilen keine einzige Eintragung.
Gleichzeitig lag der Status in DynamoDB und wurde per
`tracker setze <referenz> <status>` gepflegt, also genau dort, wo man
gerade *nicht* ist, wenn man die Tabelle durchgeht.

## Entscheidung

### Die Deckung wird gedämpft

`punkte = 100 * erreicht / (möglich + 5)`.

Der Zuschlag im Nenner kostet dünne Anzeigen unverhältnismäßig viel:

| Deckung | vorher | nachher |
|---------|--------|---------|
| 3 / 3 | 100 | 38 |
| 4 / 4 | 100 | 44 |
| 6 / 8 | 75 | 46 |
| 12 / 15 | 80 | 60 |
| 20 / 25 | 80 | 67 |

Die Rangfolge stimmt damit: eine Anzeige muss Substanz *und* Deckung
haben, um oben zu landen. Die Schwelle für A sinkt entsprechend von 60
auf 55.

Verworfen: eine Mindestzahl an Begriffen für Stufe A. Das wäre eine
harte Kante gewesen, die dieselbe Anzeige bei einem Begriff mehr
schlagartig um zwei Stufen hebt. Die Dämpfung wirkt stetig.

Der Wert 5 ist **gesetzt, nicht gemessen** — wie die Schwellen davor.
Der Unterschied ist, dass es jetzt etwas gibt, woran man ihn messen kann.

### `rueckblick` schließt die Rückkopplung

Der Bewerbungsstatus lag seit Beginn in DynamoDB und wurde von nichts
ausgewertet. `tracker rueckblick` stellt Punktebänder gegen die
tatsächlichen Ausgänge:

```
Punkte    beworben  Interview  Zusage  Absage  offen   Quote
70-100          12          5       1       6      0     50%
55-69           18          3       0      12      3     20%
```

Dazu die Gegenprobe: liegt der Punkteschnitt der als *nicht interessant*
verworfenen Anzeigen über dem der abgeschickten, misst die Bewertung das
Falsche — und der Befehl sagt das.

Gerechnet wird **neu** statt gespeichert. Ändert sich die Formel oder
wächst das Profil, soll der Rückblick die heutige Bewertung beurteilen,
nicht die von damals. Der Preis ist ein Archivdurchlauf je Aufruf; bei
einigen hundert Anzeigen aus dem Zwischenspeicher ist das vertretbar.

### Die Tabelle wird zum Eingabefeld

Die Spalte `Status` bekommt ein Auswahlfeld (Excel-Datenprüfung) mit
fünf Werten. Der Export liest sie **vor** dem Schreiben zurück nach
DynamoDB — sonst überschriebe der Lauf die eigene Eingabe.

Damit dreht sich die Datenrichtung für genau eine Spalte um. Das ist der
Grund, warum sie trotzdem unter „automatisch" steht: nach dem Rückweg
ist DynamoDB wieder die Wahrheit, und von dort wird geschrieben wie bei
jeder anderen Spalte auch.

Ein Zellinhalt, den die Liste nicht kennt, wird gemeldet und übergangen,
nicht geraten. Das Auswahlfeld verhindert ihn im Normalfall ohnehin.

**`Nicht interessant` blendet die Zeile aus.** Der Eintrag bleibt in
DynamoDB und verliert seine Aufbewahrungsfrist — würde er ablaufen, käme
dieselbe Anzeige beim nächsten Lauf zurück. Genau dafür ist der Zustand
da.

### Handspalten entfallen

`Datum Abgabe`, `Frist Rückmeldung`, `Datum Rückmeldung` und `Notizen`
sind raus; `Bewerbungsweg` ebenfalls, weil er nach der Umstellung auf
„nur der abweichende Kanal" in vier von fünf Zeilen leer stand. Von 22
Spalten bleiben 17.

Die Fristen fehlen dabei nicht: wann ein Status zuletzt geändert wurde,
steht in DynamoDB. `tracker faellig` beantwortet daraus „seit 21 Tagen
keine Rückmeldung", ohne dass jemand ein Datum eintippt. Eine Frist, die
sich selbst pflegt, ist besser als eine, die niemand pflegt.

## Kleineres im selben Zug

**Gehalt aus dem Anzeigentext.** Die Strukturfelder stehen praktisch
immer auf `KEINE_ANGABEN` (ADR 0005). Gemessen an 44 Anzeigen nennen
aber 7 % einen Betrag und 2 % eine Entgeltgruppe im Fließtext. Zwei
Muster holen das heraus — wenig, aber vorher war es null.

**Entfernung ohne Kartendienst.** Die Bundesagentur liefert sie mit, die
übrigen Börsen nennen nur einen Ortsnamen. Statt eines
Postleitzahlenverzeichnisses (achttausend Einträge) steht in
`gemeinsam/entfernung.py` eine Liste der größten Städte plus Hamburger
Umland; gerechnet wird die Luftlinie. Was nicht in der Liste steht,
bekommt keine Entfernung — eine leere Zelle ist besser als eine falsche
Zahl, und Regionen wie „EMEA" brauchen ohnehin keine.

**Der blinde Fleck des Verzeichnisses.** `faehigkeiten.py` ist eine feste
Liste; was nicht darin steht, taucht weder in der Bewertung noch im
Skill-Trend auf. `gemeinsam/begriffe.py` sammelt deshalb Kandidaten aus
den Anzeigentexten — Abkürzungen, Binnenmajuskeln, Namen mit
Sonderzeichen —, zieht Bekanntes und eine Stoppliste ab und zeigt den
Rest im `trend`. An echten Anzeigen fand das DB2, COBOL, JCL, GitOps und
XML. Ein Vorschlagswesen, keine Erkennung: was davon hineingehört,
entscheidet ein Mensch.

## Konsequenzen

Eine bestehende Tabelle im alten Schema behält ihre alten Spalten als
fremde, nie wieder gefüllte. Wo nichts von Hand eingetragen ist, ist der
saubere Weg, die Datei zu löschen und neu zu exportieren.

Der Export schreibt jetzt nach DynamoDB, nicht nur daraus. Ein Lauf gegen
eine veraltete Tabellenkopie könnte damit einen Status zurückdrehen — in
einem Werkzeug für einen Rechner und einen Benutzer ist das hinnehmbar,
in einem geteilten wäre es das nicht.
