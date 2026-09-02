# ADR 0006: Bundesweite Suche nach vollstaendig remote zu erledigenden Stellen

Datum: 2026-09-01
Status: akzeptiert

## Kontext

Die Suche war auf 30 km um Hamburg beschraenkt. Bei einer Stelle, die
vollstaendig aus dem Homeoffice erledigt wird, spielt der eingetragene
Arbeitsort aber keine Rolle - solche Anzeigen fielen bisher durchs
Raster, egal wie gut sie passten.

## Wie die API Homeoffice abbildet

Der in der Dokumentation genannte Filter `arbeitszeit=ho`
(HEIM_TELEARBEIT) ist **wirkungslos**. Er liefert null Treffer, auch bei
33.844 Hamburger Anzeigen ohne Filter, und die Facette `arbeitszeit`
kennt nur noch `vz`, `tz` und `snw`.

Ein Parameter `homeoffice` existiert nicht; jeder Versuch endet mit
HTTP 400. Auch die OpenAPI-Spezifikation im Repository hilft nicht
weiter - sie fuehrt noch einen Parameter `corona`.

Die Information steckt stattdessen in der Antwort selbst, in drei
Feldern je Anzeige:

| Feld | Werte |
|------|-------|
| `homeofficemoeglich` | true / false / fehlt |
| `homeofficetyp` | `NACH_VEREINBARUNG` / `ANGABE_IN_PROZENT` / fehlt |
| `homeofficeprozent` | Zahl, nur bei `ANGABE_IN_PROZENT` |

Verteilung in einer Stichprobe von 1441 Anzeigen:

| | Anzahl |
|---|---|
| ohne jede Angabe | ~1300 |
| `NACH_VEREINBARUNG` | 121 |
| mit Prozentwert | 15 |
| davon **100 Prozent** | **5** |

## Entscheidung

Der Poller macht einen zweiten Durchgang ohne `wo` und `umkreis`, also
bundesweit, und behaelt daraus nur Anzeigen mit
`homeofficeprozent >= 100`.

Gefiltert wird im Poller, nicht im Consumer. Der bundesweite Suchraum
ist eine Eigenschaft der Suche; alles ungefiltert durch Kafka zu
schicken hiesse, mehrere hundert Anzeigen pro Lauf zu transportieren und
in DynamoDB zu schreiben, von denen fast keine in Frage kommt.

**`NACH_VEREINBARUNG` gilt nicht als remote.** Der Wert sagt nur, dass
darueber gesprochen werden kann. Fuer eine Stelle am anderen Ende der
Republik ist das keine Grundlage - im Umkreis von Hamburg ist es
dagegen unerheblich, weil solche Anzeigen ohnehin ueber den ersten
Durchgang kommen.

Die Schwelle ist ueber `JOBSUCHE_REMOTE_MIN_PROZENT` einstellbar. Ein
niedrigerer Wert laesst auch teilweise remote zu arbeitende Stellen zu -
dann ist die Entfernung zum Arbeitsort allerdings wieder ein Thema.

## Konsequenzen

Der zweite Durchgang kostet wenige zusaetzliche Anfragen: gemessen 15
statt 9 pro Lauf, weil das Zeitfenster von sieben Tagen auch bundesweit
stark eingrenzt.

Die Ausbeute ist klein. In der Messung kamen zwei zusaetzliche Anzeigen
dazu, eine davon fiel danach durch den Senior-Ausschluss. Das liegt
nicht an der Suche, sondern daran, dass kaum ein Arbeitgeber die
Prozentangabe pflegt - `NACH_VEREINBARUNG` ist achtmal haeufiger.

Wer den Blick weiten will, setzt die Schwelle herunter oder nimmt
`NACH_VEREINBARUNG` hinzu. Das waere allerdings eine andere Zusage als
"vollstaendig remote".
