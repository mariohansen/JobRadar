# ADR 0008: Tabelle nach Passung sortiert, Gehaltsschätzung raus

Datum: 2026-09-03
Status: akzeptiert

## Kontext

Der erste Lauf gegen den vollen Bestand brachte 339 Anzeigen in die
Tabelle - unsortiert in Fundreihenfolge, mit 337 davon auf der Stufe
„D – zu wenig Angaben". Drei Dinge waren dafür verantwortlich:

1. **Die Detailansicht wurde nie ausgewertet.** Die Schnittstelle hat das
   Beschreibungsfeld von `stellenbeschreibung` auf
   `stellenangebotsBeschreibung` umbenannt. Ohne Anzeigentext hat die
   Passung nichts zu vergleichen und fällt für fast jede Anzeige auf „zu
   wenig Angaben" - genau der Fall, den [ADR 0007](0007-anreicherung-im-filter-dedup.md)
   vermeiden wollte. Betroffen waren ebenso Benefits und Kontakt.

2. **Die Gehaltsspalte war Rauschen.** `--gehalt-schaetzung` trug den
   Median des Entgeltatlas ein - der hängt nur an Berufsgruppe, Niveau
   und Region und war damit für ganze Blöcke von Anzeigen wortgleich, in
   einem Fall „Spezialist" (6461) über „Experte" (6329).

3. **Die Reihenfolge trug keine Information.** Wer eine nach Treffern
   geordnete Liste erwartet, findet die Anzeige an Position 1 neben der an
   Position 300 gleich unbewertet.

## Entscheidung

**Feldname nachgezogen.** `gemeinsam.anzeige.beschreibung()` probiert
`stellenangebotsBeschreibung`, dann `stellenbeschreibung`. Dieselbe
Mehr-Namen-Strategie wie beim Kontaktblock (ADR 0001). Der Fix sitzt im
gemeinsamen Code und wirkt damit auch auf die Anreicherung im
`filter-dedup` und die Bewertung in der Mail.

**Der Export sortiert nach Passung.** Mit Profil ordnet `excel.schreibe`
die Datenzeilen am Ende jedes Laufs: Stufe A vor D, innerhalb einer Stufe
nach Punkten, dann nach Alter und Firma. Die `Nr.` ist danach der Rang.

Sortiert wird die **volle Zeilenbreite**. Handeinträge (Termine, Notizen)
und fremde Spalten wandern so mit ihrer Anzeige mit, zugeordnet über die
versteckte `Referenz`-Spalte. Der Preis: zeilenbezogene Handformatierung
und Formeln mit Zeilenbezug überstehen das Umsortieren nicht. Für einen
Tracker ohne solche Formeln ist das vertretbar, und die Sicherung neben
der Datei bleibt.

Ohne Profil - keine Passungsspalte - bleibt die Fundreihenfolge.

**Die Gehaltsschätzung ist raus.** `--gehalt-schaetzung`, `Gehaltsschaetzer`
und `lade_schaetzer` entfallen. Die Spalte `Gehalt` bleibt und wird nur
noch aus einer echten Angabe der Anzeige oder dem Tarifvertrag gefüllt -
in der Praxis fast nie, was der Datenlage entspricht. `salary-check`
bleibt als eigenständiges Werkzeug (Nachtrag in ADR 0005).

**Spalten entschlackt.** „Nächster Schritt" (war 1:1 aus dem Status
abgeleitet) entfällt. „Ansprechpartner" und „Kontakt (E-Mail/Telefon)"
werden zu einer Spalte `Kontakt`. „Notizen" wird nicht mehr automatisch
befüllt (Fund-/Veröffentlichungsdatum dopplten `Alter (Tage)`), sondern
ist Handarbeit. „Bewerbungsweg" bleibt leer, wenn die Bewerbung wie
üblich über die Jobbörse läuft, und nennt nur den abweichenden Kanal.

**Der Titel-Ausschluss der Pipeline gilt auch im Tracker.** Der
Dedup-Schritt legt jede *gesehene* Anzeige in DynamoDB an - bevor der
Filter läuft, weil dieselbe unpassende Anzeige sonst jeden Poller-Lauf
neu abgerufen würde. Die `SEEN_JOBS`-Tabelle ist damit „gesehen", nicht
„gematcht", und der Export zeigte Senior- und Lead-Stellen, die die Mail
zu Recht verschwiegen hat.

Die Ausschlussbegriffe und die Wortanfang-Prüfung ziehen nach
`gemeinsam.ausschluss`; `filter-dedup` und `tracker` lesen dieselbe
Variable `MATCH_AUSSCHLUSS`. `tracker liste` und `tracker export` wenden
sie auf den Titel an: betroffene Anzeigen im Status `GEFUNDEN` kommen
nicht in die Tabelle, bereits vorhandene solche Zeilen werden beim
nächsten Lauf entfernt. Alles ab `BEWORBEN` bleibt - daran hängt Arbeit.
`--mit-aussortierten` schaltet den Filter ab.

Verworfen: die Anzeigen aus DynamoDB löschen. Sie lägen nach dem
nächsten Poller-Lauf wieder da (das Suchfenster ist sieben Tage), und
der Dedup-Schritt verlöre seinen Zweck.

## Verworfene Alternativen

**Reihenfolge fix lassen, nur eine Rang-Spalte ergänzen.** Excel kann
nach ihr sortieren. Aber „schon einsortiert" war die Anforderung - eine
Spalte, die man erst anklicken muss, erfüllt sie nicht.

**Die Schätzung knapper darstellen** statt sie zu entfernen. Ändert
nichts daran, dass in dreißig Zeilen derselbe Wert steht.

**Beim Umsortieren die Zellformate mitführen.** openpyxl gibt das her,
aber der Aufwand steht in keinem Verhältnis zu einer Tabelle, die keine
zeilenweise Formatierung trägt.

## Konsequenzen

Eine bestehende Tabelle im alten Schema behält ihre alten Spalten als
fremde, nie wieder gefüllte Spalten. Wo noch nichts von Hand eingetragen
ist, ist der saubere Weg, die Datei zu löschen und neu zu exportieren.
Die Zuordnung über Überschriften trägt den Rest: eigene Spalten und
Umsortierungen bleiben gefahrlos.
