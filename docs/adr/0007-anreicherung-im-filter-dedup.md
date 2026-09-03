# ADR 0007: Anreicherung und Bewertung im filter-dedup

Datum: 2026-09-03
Status: akzeptiert

## Kontext

Die Benachrichtigungsmail soll erkennen lassen, wie gut eine Anzeige zum
eigenen Profil passt, damit bei zwölf Treffern die drei wichtigen oben
stehen. Dafür braucht es zwei Dinge, die bisher nirgends in der Pipeline
vorlagen:

* den **Anzeigentext**. Die Trefferliste der Jobsuche enthält ihn nicht
  ([ADR 0001](0001-datenquelle-jobsuche-api.md)); ohne ihn bleiben nur
  Titel und Berufsbezeichnung, und fast jede Anzeige wäre „zu wenig
  Angaben".
* das **Fähigkeitsprofil**, das bislang nur auf dem eigenen Rechner lag.

Damit stand die Frage, welche Stufe der Pipeline den Text holt und die
Bewertung rechnet.

## Entscheidung

Der `filter-dedup` reichert an, **nach** Dedup und Filter und **nach**
dem Archivieren. Das Ergebnis hängt unter dem Schlüssel `jobradar` an der
Nachricht nach `jobs.matched`. Der `notifier` stellt es nur noch dar.

```
archivieren (roh)  ->  dedup  ->  filter  ->  anreichern  ->  jobs.matched
```

Drei Gründe für diese Stelle:

**Der Abruf fällt einmal je wirklich neuer Anzeige an.** Vor dem
Dedup-Schritt wäre dieselbe Anzeige im Suchfenster von sieben Tagen
mehrfach abgerufen worden; im `notifier` wäre er einmal je Nachricht
angefallen, also nach jedem erneuten Zustellen.

**Der Zwischenspeicher wird von selbst warm.** Der Text landet unter
`detail/` im selben Archiv, aus dem sich der Export auf dem eigenen
Rechner bedient. Der muss deshalb gar nichts mehr abrufen — die Anzeige
war schon da, bevor die Mail ankam.

**Der notifier bleibt ein reiner Formatierer.** Er braucht weder Profil
noch Netzzugriff und rechnet nichts aus. Fehlt der Zusatz, fällt die Mail
auf ihre bisherige Form zurück.

Archiviert wird weiterhin **vor** der Anreicherung. Das Archiv soll die
Anzeige so halten, wie die Schnittstelle sie geliefert hat; eine spätere
Auswertung soll nicht auf einer Bewertung von heute sitzen, die morgen
mit einem gewachsenen Profil anders ausfiele.

## Verworfene Alternativen

**Anreichern im notifier.** Hätte den Consumer unverändert gelassen, aber
den Abruf an die Zustellung gekoppelt statt an die Anzeige. Bei einem
Neustart mit unbestätigten Offsets wäre derselbe Text mehrfach geholt
worden.

**Anreichern im poller.** Dort ist noch nicht bekannt, welche Anzeigen
neu sind. Bei rund hundert Treffern je Lauf und alle zehn Stunden wären
das einige tausend Abrufe pro Woche gegen eine Schnittstelle, hinter der
kein Vertrag steht.

**Ein eigener Anreicherungs-Consumer** mit einem Topic dazwischen. Sauber
getrennt, aber ein dritter Dienst und ein drittes Topic auf einer
t3.micro mit 1 GiB RAM — Aufwand, den ein Feld in einer Nachricht nicht
rechtfertigt.

## Der gemeinsame Code

Verzeichnis, Profil, Bewertung und Archivzugriff brauchen jetzt zwei
Seiten: der `filter-dedup` auf der Instanz und der `tracker` auf dem
eigenen Rechner. Sie liegen deshalb in `services/gemeinsam/` und werden
mit ausgerollt.

Besonders der Archivzugriff gehört dorthin: Schreiber und Leser müssen
sich über das Ablageschema einig sein. Lägen `raw/jahr=…/monat=…/tag=…`
in zwei Dateien, fände der Export die Rohdaten nach der ersten
einseitigen Änderung nicht mehr — und zwar lautlos.

## Das Profil verlässt den Rechner

Für die Bewertung in der Mail muss das Profil auf die Instanz. Das
Ausrollskript legt `bewerbung/profil.json` unter `/opt/jobradar/` ab und
setzt `JOBRADAR_PROFIL`.

Es enthält keine Unterlagen, sondern nur die daraus erkannten
Schlagwörter — trotzdem ist es eine bewusste Entscheidung und kein
Nebeneffekt. Fehlt die Datei, läuft die Pipeline wie zuvor, nur ohne
Bewertung. Lebenslauf und Zeugnisse bleiben in jedem Fall lokal.

## Konsequenzen

Der `filter-dedup` spricht jetzt mit dem Internet, nicht mehr nur mit
AWS. Das ist eine neue Fehlerquelle in einem Consumer, der bisher keine
hatte, und deshalb vollständig gekapselt: `sicher_ergaenzen` fängt jede
Ausnahme ab und lässt die Anzeige unangereichert weiterlaufen. Eine Mail
ohne Bewertung ist besser als keine Mail.

Mit `FILTER_DETAILS=false` lässt sich der Abruf ganz abschalten; dann
fehlen Bewertung und Anzeigentext, alles andere bleibt.
