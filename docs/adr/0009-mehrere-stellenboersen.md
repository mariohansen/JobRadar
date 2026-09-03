# ADR 0009: Mehrere Stellenbörsen, eine Deduplizierung

Datum: 2026-09-03
Status: akzeptiert

## Kontext

Die Jobsuche der Bundesagentur ist eine gute, aber nicht die einzige
Quelle. Viele Arbeitgeber melden ihre Stellen dort gar nicht — gerade im
IT-Bereich und gerade die vollständig entfernt zu erledigenden. Bei rund
anderthalb neuen Treffern pro Tag ist der Bestand schmal genug, dass eine
zweite und dritte Quelle spürbar etwas ändert.

Damit stellten sich drei Fragen: **welche** Börsen, in **welchem Format**
sie ankommen, und wie verhindert wird, dass dieselbe Stelle drei- oder
viermal gemeldet wird.

## Welche Börsen — und welche nicht

Aufgenommen sind sechs Anbieter mit **offener, dokumentierter
Schnittstelle**:

| Name | Bestand | Zugangsdaten |
|------|---------|--------------|
| `arbeitsagentur` | Hamburg + bundesweit remote | – |
| `arbeitnow` | Deutschland | – |
| `adzuna` | Deutschland, Aggregator | kostenlose Registrierung |
| `remotive` | weltweit remote | – |
| `remoteok` | weltweit remote | – |
| `jobicy` | remote, Region Deutschland | – |

**Nicht aufgenommen: LinkedIn, Indeed, StepStone, get-in-it.** Sie haben
keine offene Schnittstelle für diesen Zweck, ihre Nutzungsbedingungen
untersagen automatisiertes Auslesen, und LinkedIn wie Indeed setzen das
technisch wie juristisch durch. Ein Scraper dagegen wäre ein absehbar
gesperrter Poller — und das Risiko läge beim Betreiber persönlich, nicht
beim Projekt. Der Verzicht kostet Abdeckung; Adzuna aggregiert einen Teil
desselben Marktes auf zulässigem Weg.

## Ein Format statt sechs

Jede Quelle übersetzt ihr Ergebnis in **das Format der Jobsuche-API**,
statt dass ein neutrales eigenes Schema entsteht. Das ist bewusst die
unelegantere Lösung: sauberer wäre ein eigenes Modell, dem alle Quellen
gleich fern stehen.

Dagegen stand, dass dieses Format bereits an vier Stellen gelesen wird —
`filter-dedup`, Anreicherung, Benachrichtigung, Tracker-Export. Ein
neutrales Schema hätte alle vier gleichzeitig ändern müssen. So bleibt
flussabwärts alles unverändert, und eine neue Quelle ist genau eine
Datei in `services/poller/poller/quellen/`.

Zwei Felder kommen hinzu: `quelle` nennt die Herkunft, und
`referenznummer` trägt sie als Präfix (`arbeitnow:slug-123`). Die
Referenznummern der Bundesagentur bleiben **ohne** Präfix — an ihnen
hängen das Archiv, die Detailabrufe und die vorhandenen Tracker-Zeilen.

## Deduplizierung auf zwei Ebenen

Der bisherige Abgleich läuft über die Referenznummer. Die ist nur
*innerhalb* einer Quelle eindeutig: dieselbe Stelle hat bei der
Bundesagentur eine andere Kennung als auf Arbeitnow.

Dazu kommt deshalb ein **inhaltlicher Fingerabdruck** aus Arbeitgeber,
Titel und Ort — normalisiert, weil dieselbe Stelle je nach Portal anders
geschrieben steht:

```
"Data Engineer (m/w/d)"   ≙  "Data Engineer (w/m/d)"
"Beispiel GmbH & Co. KG"  ≙  "Beispiel GmbH"
"20095 Hamburg"           ≙  "Hamburg, Deutschland"
```

Erfahrungsstufen werden **nicht** wegnormalisiert: „Senior Data
Engineer" und „Data Engineer" sind verschiedene Stellen.

Geprüft wird an zwei Stellen:

* **im Poller**, innerhalb eines Laufs — damit dieselbe Stelle nicht
  mehrfach nach `jobs.raw` geht;
* **im filter-dedup**, über Läufe hinweg — als zweiter bedingter
  Schreibvorgang gegen dieselbe DynamoDB-Tabelle, unter dem Schlüssel
  `fp#<abdruck>`.

Der zweite Schreibvorgang braucht **kein neues Schema und keinen Index**:
er nutzt denselben Partitionsschlüssel, nur in einem eigenen Namensraum.
Ein Eintrag `fp#…` ist keine Anzeige, sondern die Notiz, dass es eine mit
diesem Inhalt schon gibt; er notiert, welche zuerst da war. Der Tracker
überspringt diese Merkposten beim Lesen.

Verworfen wurde ein globaler Sekundärindex auf den Fingerabdruck:
sauberer abfragbar, aber eine zusätzliche Abfrage je Anzeige und eine
Schemaänderung — für einen Vergleich, den ein bedingter Schreibvorgang
atomar und kostenlos miterledigt.

Fehlt Arbeitgeber oder Titel, entsteht **kein** Fingerabdruck. Ein zu
grober Schlüssel würde fremde Stellen zusammenwerfen; dann lieber der
Abgleich über die Kennung allein und im Zweifel eine Meldung zu viel.

## Der Anzeigentext kommt jetzt meistens mit

Die Trefferliste der Bundesagentur enthält keinen Text (ADR 0001),
weshalb `filter-dedup` ihn einzeln nachlädt (ADR 0007). Die übrigen
Börsen liefern ihn gleich mit. `anzeige.beschreibung` sucht deshalb in
beidem — Detailansicht und Anzeige selbst —, und der Nachladeschritt
entfällt, wo schon Text dasteht. Für diese Quellen ist die
Passungsbewertung ohne einen einzigen Zusatzabruf zu haben.

## Zurückhaltung

Diese Schnittstellen sind kostenlos und ohne Vertrag; Arbeitnow bittet
ausdrücklich darum, sie nicht zu überlasten. Beim Entwickeln hat sie
prompt mit HTTP 429 geantwortet. Deshalb: höchstens drei Seiten je
Quelle, eine Sekunde Pause dazwischen, und ein 429 beendet die
Paginierung sauber, statt den Lauf zu kippen. Fällt eine Quelle ganz aus,
laufen die übrigen weiter — dieselbe Kapselung wie bei der Anreicherung.

## Konsequenzen

Der Poller spricht jetzt mit sechs Gegenstellen statt einer. Jede ist
eine eigene Fehlerquelle, jede einzeln gekapselt.

Die meisten dieser Börsen kennen keine Feldsuche; gefiltert wird nach dem
Abruf über die Suchbegriffe aus `JOBSUCHE_WAS`. Mit einem einzigen
Begriff bleibt von ihnen wenig übrig — sie lohnen sich erst mit mehreren.
Voreingestellt sind deshalb fünf: `Data Engineer`, `Softwareentwickler`,
`Software Engineer`, `Developer`, `Java`.

Der Titelfilter vergleicht **Teilzeichenketten**, nicht Wortgrenzen —
deutsche Stellentitel schreiben zusammen, und `entwickler` fände
„Softwareentwickler" nicht. Das kollidiert bei kurzen Begriffen:
„Java" steckt auch in „JavaScript", einer anderen Sprache. Gelöst über
das Fähigkeitsverzeichnis: nennt ein Suchbegriff genau einen
Katalogeintrag, gilt dessen bereits geprüftes Muster (`java`) statt
der Teilzeichenkette. Für alles, was nicht im Katalog steht — „Developer",
„Softwareentwickler" —, bleibt es beim Teilstringvergleich.

Der Lambda-Build packt jetzt `services/gemeinsam/` mit ein: Poller und
`filter-dedup` müssen denselben Fingerabdruck berechnen. Zwei Kopien
liefen nach der ersten einseitigen Änderung lautlos auseinander, und die
quellenübergreifende Deduplizierung wäre still kaputt.
