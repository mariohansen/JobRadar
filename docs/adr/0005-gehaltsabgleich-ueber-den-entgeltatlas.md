# ADR 0005: Gehaltsabgleich ueber den Entgeltatlas

Datum: 2026-08-31
Status: akzeptiert; im Tracker-Export zurueckgenommen (ADR 0008)

> **Nachtrag ([ADR 0008](0008-tabelle-nach-passung-sortiert.md)):** Die
> Schaetzung wurde als Spalte des Exports wieder entfernt. Der Median ist
> fuer alle Anzeigen einer Berufsklasse in einer Region derselbe und
> stand deshalb in Dutzenden Zeilen wortgleich, teils widerspruechlich
> ("Spezialist" ueber "Experte"). `salary-check` bleibt als eigenes
> Werkzeug fuer die gezielte Einzelabfrage - die Entscheidungen unten
> gelten dort unveraendert.

## Kontext

Zu einer Stellenanzeige gehoert die Frage, was in diesem Beruf ueblich
gezahlt wird. Die Anzeigen selbst schweigen dazu meist: das Feld
`verguetungsangabe` steht bei den beobachteten Treffern durchgaengig auf
`KEINE_ANGABEN`.

Die Bundesagentur betreibt mit dem Entgeltatlas eine Datenbank ueber
Bruttoentgelte nach Beruf, Region, Branche, Alter und Geschlecht.

## Entscheidung

Abgefragt wird
`https://rest.arbeitsagentur.de/infosysbub/entgeltatlas/pc/v1/entgelte/{KldB}`.

Die in `bundesAPI/entgeltatlas-api` dokumentierten Zugangsdaten - eine
UUID als `client_id` samt `client_secret` und OAuth-Fluss - werden
inzwischen mit 403 abgewiesen, ebenso der dort genannte Token-Endpunkt.
Gueltig ist die clientId, die die Weboberflaeche selbst verwendet:
`infosysbub-ega`, uebergeben als Header `X-API-Key`. Sie liess sich der
Startseite unter `web.arbeitsagentur.de/entgeltatlas/` entnehmen.

Dasselbe Muster wie bei der Jobsuche (ADR 0001): die Dokumentation
hinkt der Wirklichkeit hinterher, die Oberflaeche verraet den aktuellen
Stand.

## Negative Werte sind keine Betraege

Die Schnittstelle nutzt negative Zahlen als Platzhalter:

| Wert | Bedeutung |
|------|-----------|
| `-1` | keine Daten vorhanden |
| `-2` | vorhanden, aber nicht ausweisbar |
| `-42` | erscheint anstelle einer Fallzahl |

Wer sie ungeprueft uebernimmt, erhaelt negative Gehaelter. Der Client
prueft deshalb jeden Betrag einzeln, auch die Quartile - ein einzelnes
Quartil kann fehlen, obwohl der Median vorliegt.

## Zuordnung ist eine Heuristik

Der Entgeltatlas erwartet einen Schluessel der Klassifikation der Berufe
2010, die Jobsuche liefert Klartext. Dazwischen liegt eine Abbildung
ueber Schluesselbegriffe im Stellentitel:

- Berufsgruppe: Beratungsbegriffe wie "Consultant" oder "SAP" fuehren auf
  4321 (IT-Anwendungsberatung), sonst 4341 (Softwareentwicklung).
- Anforderungsniveau als fuenfte Ziffer: "Senior", "Lead" oder
  "Architekt" ergeben 4 (Experte), "Junior" oder "Trainee" 2
  (Fachkraft), ohne Hinweis 3 (Spezialist).

Ohne Hinweis wird bewusst der niedrigere Wert angenommen. Eine zu
optimistische Gehaltsangabe waere in einer Gehaltsverhandlung der
unangenehmere Fehler.

Belastbar waere die Zuordnung nur ueber die Berufedatenbank der
Bundesagentur. Fuer ein Projekt mit zwei Suchbegriffen steht der Aufwand
dafuer in keinem Verhaeltnis.

## Konsequenzen

Der Abgleich ist ein Anhaltspunkt, keine Aussage ueber die konkrete
Stelle. Er beruht auf Medianen ueber alle Beschaeftigten einer
Berufsgruppe in einem Bundesland - Erfahrung, Unternehmensgroesse und
Branche gehen nicht ein, obwohl die Schnittstelle eine Aufschluesselung
nach Branche anbietet.

Nicht fuer jede Kombination aus Beruf und Region liegen Werte vor. Das
Werkzeug meldet das ausdruecklich, statt eine Zahl zu erfinden.
