# ADR 0001: Jobsuche-API der Bundesagentur als Datenquelle

Datum: 2026-08-31
Status: akzeptiert

## Kontext

JobRadar braucht eine Quelle fuer neue Stellenanzeigen im Raum Hamburg.
Scraping gegen StepStone, Indeed oder LinkedIn scheidet aus, weil es deren
Nutzungsbedingungen verletzt.

Die Bundesagentur fuer Arbeit betreibt die groesste Stellendatenbank
Deutschlands und stellt sie ueber die Endpunkte ihrer eigenen Jobsuche-App
bereit. Eine offizielle, dokumentierte API gibt es nicht; die Endpunkte
sind aber oeffentlich erreichbar und in `bundesAPI/jobsuche-api`
dokumentiert.

## Entscheidung

Datenquelle ist `GET /jobboerse/jobsuche-service/pc/v6/jobs` unter
`https://rest.arbeitsagentur.de`.

Authentifizierung erfolgt ueber den statischen Header
`X-API-Key: jobboerse-jobsuche`. Das ist eine oeffentlich bekannte
clientId, kein Geheimnis - sie gehoert daher nicht in den Secrets Manager,
sondern als normale Konfiguration in eine Umgebungsvariable.

Dedup-Schluessel ist das Feld `referenznummer` (Format `10001-1003552327-S`).

## Verifikation am 2026-08-31

Ein Request mit `was=Data Engineer`, `wo=Hamburg`, `umkreis=30` lieferte
`maxErgebnisse: 102` und valides JSON.

Relevante Felder je Treffer: `referenznummer`, `stellenangebotsTitel`,
`firma`, `stellenlokationen[].adresse`, `datumErsteVeroeffentlichung`,
`aenderungsdatum`, `alleBerufe`, `arbeitgeberKundennummerHash`.

Die Trefferliste enthaelt keinen Anzeigentext. Volltexte kommen ueber
`/pc/v4/jobdetails/{base64(referenznummer)}` und werden erst gebraucht,
wenn der CV-Matcher gebaut wird.

## Zeitfilter mit Fallstrick

Der Parameter `veroeffentlichtseit` begrenzt die Antwort auf kuerzlich
veroeffentlichte Anzeigen. Er akzeptiert aber nur die Werte **0, 1, 7, 14
und 28** - die Zeitraum-Schaltflaechen der Jobboersen-Oberflaeche.

Jeder andere Wert wird kommentarlos verworfen. Die API meldet keinen
Fehler, sondern liefert saemtliche Treffer. Gemessen am 2026-08-31 fuer
"Data Engineer" in Hamburg:

| Wert | 0 | 1 | 7 | 14 | 28 | jeder andere |
|------|---|---|---|----|----|--------------|
| Treffer | 2 | 2 | 12 | 34 | 51 | 104 |

Ein Tippfehler oder ein plausibel aussehender Wert wie 3 fuehrt also
dazu, dass der Poller unbemerkt das Vielfache an Anzeigen verschickt.
Der Poller validiert den Wert deshalb selbst und bricht bei einem
unzulaessigen ab, statt sich auf die API zu verlassen.

## Konsequenzen

Die API ist inoffiziell. Pfadversion und Feldnamen koennen sich ohne
Ankuendigung aendern - der frueher verbreitete Pfad `/pc/v4/jobs` liefert
inzwischen 403, und das Feld hiess dort noch `refnr` statt
`referenznummer`. Der Poller braucht deshalb belastbares Fehlerhandling,
und Schema-Annahmen gehoeren an eine Stelle statt verteilt in den Code.

Weil kein Vertrag und kein Support dahintersteht, wird defensiv gepollt
statt in kurzen Intervallen gehaemmert.
