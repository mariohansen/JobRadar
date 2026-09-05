# Befehle und Begriffe

Nachschlagewerk für alles, was JobRadar an Befehlen, Schaltern,
Umgebungsvariablen und festen Begriffen kennt. Das *Warum* steht im
[README](../README.md) und in den [ADRs](adr/); hier steht das *Wie*.

## Zuerst: die virtuelle Umgebung

`boto3`, `openpyxl` und `pypdf` liegen im `.venv` des Projekts, nicht im
System-Python. Ohne aktivierte Umgebung endet **jeder** Aufruf mit
`ModuleNotFoundError: No module named 'boto3'`.

```powershell
.\.venv\Scripts\Activate.ps1      # aus dem Projektverzeichnis
```

Danach steht `(.venv)` vor dem Prompt und `python` zeigt auf
`...\.venv\Scripts\python.exe` — prüfen lässt sich das mit
`(Get-Command python).Source`.

Die Aktivierung gilt nur für dieses Fenster. Wer sie umgehen will, ruft
den Interpreter direkt auf:

```powershell
..\..\.venv\Scripts\python.exe -m tracker.main profil
```

Fehlt die Umgebung noch, entsteht sie mit:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r services\tracker\requirements.txt
```

Schlägt `Activate.ps1` mit einer Richtlinienmeldung fehl, hilft einmalig
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. Bei
`RemoteSigned` — der üblichen Einstellung für den eigenen Benutzer —
tritt das nicht auf, weil das Skript lokal erzeugt wurde.

## Welche Shell

Die Beispiele stehen in **PowerShell**, weil das die Windows-Vorgabe ist.
Fünf Stellen unterscheiden sich von Bash:

| Zweck | PowerShell | Bash |
|-------|-----------|------|
| Variable setzen | `$env:NAME = wert` | `export NAME=wert` |
| Befehle verketten | `A; if ($?) { B }` | `A && B` |
| eigene IP holen | `Invoke-RestMethod https://checkip.amazonaws.com` | `curl -s https://checkip.amazonaws.com` |
| Umgebung aktivieren | `.\.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| Ausgabe einsetzen | `$(...)` – gleich | `$(...)` |

`curl` ist in Windows PowerShell ein Aliasname für `Invoke-WebRequest`
und versteht `-s` nicht. Wer das echte Programm will, ruft `curl.exe` auf.

**`-chdir` mit `..` gehört in Anführungszeichen.** Aus dem
Projektverzeichnis heraus ist `terraform -chdir=infra …` unproblematisch,
aus einem Unterverzeichnis zerlegt PowerShell den Wert aber:

```powershell
terraform -chdir=..\..\infra output -raw dedup_table_name     # Invalid -chdir option
terraform "-chdir=..\..\infra" output -raw dedup_table_name   # funktioniert
```

`scripts/deploy-consumers.sh` braucht Bash. **`bash scripts/…` reicht unter
Windows nicht**: `C:\Windows\System32\bash.exe` gehört zum
Windows-Subsystem für Linux und steht im Pfad vor Git für Windows. Ohne
installierte WSL-Distribution endet der Aufruf mit

```
Windows-Subsystem für Linux verfügt über keine installierten Distributionen.
```

Deshalb die Git-Bash direkt aufrufen:

```powershell
& "C:\Program Files\Git\bin\bash.exe" scripts/deploy-consumers.sh
```

Wo sie liegt, verrät `Get-Command bash -All`. Wer den Aufruf oft braucht,
legt sich ein Kürzel ins Profil:

```powershell
function deploy { & "C:\Program Files\Git\bin\bash.exe" scripts/deploy-consumers.sh }
```

---

## Auf einen Blick

```powershell
# im Projektverzeichnis: Umgebung aktivieren
.\.venv\Scripts\Activate.ps1

# einmalig je Sitzung: die beiden Namen, die fast alles braucht
$env:DYNAMODB_TABLE_SEEN_JOBS = terraform -chdir=infra output -raw dedup_table_name
$env:S3_BUCKET_RAW_ARCHIVE    = terraform -chdir=infra output -raw archive_bucket_name

cd services\tracker
python -m tracker.main profil                                  # Profil einlesen
python -m tracker.main liste --status BEWORBEN                 # Stand ansehen
python -m tracker.main setze 10001-1003552327-S BEWORBEN       # Status ändern
python -m tracker.main export --datei $HOME\Bewerbungs_Tracker.xlsx  # Tabelle füllen
python -m tracker.main rueckblick                              # Punktzahl vs. Ausgang
python -m tracker.main faellig --tage 21                       # ohne Rückmeldung
python -m tracker.main warum 10001-1003552327-S                # warum (nicht) dabei
python -m tracker.main trend --hochladen                       # Skill-Trend + Link

cd ..\salary-check
python -m salary_check.main --titel "Junior Data Engineer"     # Gehalt einordnen
```

In Bash stattdessen:

```bash
export DYNAMODB_TABLE_SEEN_JOBS=$(terraform -chdir=infra output -raw dedup_table_name)
export S3_BUCKET_RAW_ARCHIVE=$(terraform -chdir=infra output -raw archive_bucket_name)
```

Die Variablen gelten nur in dem Fenster, in dem sie gesetzt wurden. Nach
einem Neustart der Konsole sind sie wieder weg — dauerhaft setzen geht
mit `[Environment]::SetEnvironmentVariable("DYNAMODB_TABLE_SEEN_JOBS",
"jobradar-seen-jobs", "User")`.

---

## 1. Einrichten

| Schritt | Befehl |
|---------|--------|
| Konfiguration anlegen | `cp infra/terraform.tfvars.example infra/terraform.tfvars` |
| eigene IP ermitteln | `Invoke-RestMethod https://checkip.amazonaws.com` |
| Lambda-Paket bauen | `python services/poller/build.py` |
| Terraform vorbereiten | `terraform -chdir=infra init` |
| Infrastruktur anlegen | `terraform -chdir=infra apply` |
| Consumer ausrollen | `bash scripts/deploy-consumers.sh` (Windows: `& "C:\Program Files\Git\bin\bash.exe" scripts/deploy-consumers.sh`) |
| Umgebung anlegen | `python -m venv .venv` |
| Umgebung aktivieren | `.\.venv\Scripts\Activate.ps1` |
| Abhängigkeiten lokal | `pip install -r services\tracker\requirements.txt` |

Die Abhängigkeiten des `tracker` decken alles ab, was lokal läuft:
`boto3` für DynamoDB und S3, `openpyxl` für den Export, `pypdf` für das
Profil. `salary-check` kommt mit der Standardbibliothek aus.

AWS schickt zwei Bestätigungsmails – eine fürs Budget, eine für die
SES-Adresse. Ohne Quittung bleiben Warnungen und Benachrichtigungen aus.

### Terraform-Ausgaben

Alles, was die Werkzeuge an Namen brauchen, liefert
`terraform -chdir=infra output -raw <name>`:

| Ausgabe | Wofür |
|---------|-------|
| `dedup_table_name` | `DYNAMODB_TABLE_SEEN_JOBS` |
| `archive_bucket_name` | `S3_BUCKET_RAW_ARCHIVE` |
| `kafka_bootstrap_servers` | `KAFKA_BOOTSTRAP_SERVERS` |
| `kafka_sasl_username` | `KAFKA_SASL_USERNAME` |
| `kafka_password_ssm_parameter` | `KAFKA_PASSWORD_SSM_PARAMETER` |
| `kafka_ca_certificate_ssm_parameter` | `KAFKA_CA_CERT_SSM_PARAMETER` |
| `kafka_ca_certificate` | CA-Zertifikat im Klartext |
| `kafka_public_dns` | SSH-Ziel, muss der DNS-Name sein (nicht die IP) |
| `kafka_public_ip` | ändert sich nach jedem Stop/Start |
| `kafka_ssh_command` | fertiger SSH-Befehl |
| `kafka_instance_id` | zum Stoppen und Starten der Instanz |
| `poller_function_name` | für `aws lambda invoke` |
| `poller_log_group` | für `aws logs tail` |
| `poller_schedule` | aktiver Zeitplan |
| `notification_email` | Absender und Empfänger in SES |
| `vpc_id`, `public_subnet_id` | Netzwerk |

---

## 2. `tracker` – Bewerbungen verwalten

Aufruf aus `services/tracker`, Modul `tracker.main`.

Braucht `DYNAMODB_TABLE_SEEN_JOBS`; `export` und `trend` zusätzlich
`S3_BUCKET_RAW_ARCHIVE`. `profil` braucht keins von beidem.

### `liste` – Übersicht

```powershell
python -m tracker.main liste
python -m tracker.main liste --status BEWORBEN
```

| Schalter | Bedeutung |
|----------|-----------|
| `--status STATUS` | nur diesen Status |
| `--mit-aussortierten` | auch Anzeigen zeigen, deren Titel unter den Ausschluss fällt |

Ohne `--mit-aussortierten` blendet `liste` – wie `export` – Anzeigen aus, deren
**Titel** einen Ausschlussbegriff enthält (`senior`, `lead`, `praktikum` …, siehe
Abschnitt 4), solange sie noch im Status `GEFUNDEN` sind. Am Ende steht eine
Zeile `Aussortiert (Titel): 98 (senior: 71, lead: 9, …)`.

### `zeige` – eine Anzeige im Detail

```powershell
python -m tracker.main zeige 10001-1003552327-S
```

### `setze` – Status ändern

```powershell
python -m tracker.main setze 10001-1003552327-S BEWORBEN
```

Der Regelweg ist inzwischen das **Auswahlfeld in der Tabelle** (Spalte
`Status`); `setze` bleibt für die Kommandozeile. Angenommen wird beides,
der interne Name (`BEWORBEN`) und der Text aus der Tabelle
(`Abgeschickt`).

Sobald eine Anzeige `GEFUNDEN` verlässt, entfällt ihre
Aufbewahrungsfrist – der Eintrag bleibt dauerhaft erhalten. Das gilt
auch für `Nicht interessant`: sonst taucht dieselbe Anzeige beim
nächsten Lauf wieder auf.

### `rueckblick` – was aus den Bewerbungen wurde

```powershell
python -m tracker.main rueckblick
```

Stellt die Punktzahl gegen den tatsächlichen Ausgang – die einzige Art,
die Passungsschwellen zu prüfen, statt sie zu behaupten:

```
Punkte    beworben  Interview  Zusage  Absage  offen   Quote
70-100          12          5       1       6      0     50%
55-69           18          3       0      12      3     20%
35-54            9          0       0       9      0      0%

Als 'Nicht interessant' verworfen: 34, im Schnitt 41 Punkte
Abgeschickt dagegen im Schnitt 58 Punkte
```

Liegt der Schnitt der verworfenen Anzeigen **über** dem der
abgeschickten, misst die Bewertung das Falsche – dann sagt der Befehl das
auch. Unter zehn Rückmeldungen ist jede Quote Zufall, worauf er ebenfalls
hinweist.

Neu gerechnet statt gespeichert: ändert sich die Formel oder wächst das
Profil, beurteilt der Rückblick die **heutige** Bewertung.

| Schalter | Vorgabe | Bedeutung |
|----------|---------|-----------|
| `--profil DATEI` | `bewerbung/profil.json` | Profil für die Bewertung |
| `--ohne-details` | aus | ohne Anzeigentexte – schneller, aber gröber |

### `faellig` – Bewerbungen ohne Rückmeldung

```powershell
python -m tracker.main faellig
python -m tracker.main faellig --tage 21
```

Braucht keine handgepflegte Frist: wann der Status zuletzt geändert
wurde, steht ohnehin in DynamoDB. Gezeigt wird alles auf `Abgeschickt`
oder `Interview`, das seit mindestens `--tage` (Vorgabe 14) liegt.

### `warum` – warum steht diese Anzeige (nicht) in der Tabelle

```powershell
python -m tracker.main warum 10001-1003552327-S
```

Geht dieselben vier Stufen durch wie die Pipeline und sagt bei jeder,
was sie entschieden hat:

```
1. Bekannt?    ja, erfasst am 2026-08-31
   Status:     noch nichts entschieden
   Titel:      Senior Data Engineer (m/w/d)
   Quelle:     arbeitsagentur
2. Doppelt?    nein, Fingerabdruck fp#cc0d596f… ist frei.
3. Ausschluss? ja - der Titel enthaelt 'senior'.
4. Passung:    C – Randbereich (28 Punkte)
```

Erspart die Fehlersuche über `journalctl` auf der Instanz.

### `profil` – Fähigkeiten aus den eigenen Unterlagen

```powershell
python -m tracker.main profil              # einlesen und ablegen
python -m tracker.main profil --anzeigen   # nur ausgeben, nichts ändern
```

| Schalter | Vorgabe | Bedeutung |
|----------|---------|-----------|
| `--unterlagen VERZ` | `bewerbung/` im Projektordner | wo Lebenslauf und Zeugnisse liegen |
| `--datei DATEI` | `bewerbung/profil.json` | wohin das Profil geschrieben wird |
| `--anzeigen` | aus | vorhandenes Profil ausgeben, ohne neu zu lesen |

Gelesen werden `.pdf`, `.txt` und `.md`. Eingescannte PDFs haben keine
Textebene – das meldet der Befehl und überspringt sie.

### `export` – Bewerbungstabelle füllen

```powershell
python -m tracker.main export --datei $HOME\Bewerbungs_Tracker.xlsx
```

| Schalter | Vorgabe | Bedeutung |
|----------|---------|-----------|
| `--datei DATEI` | **Pflicht** | Zieldatei (`.xlsx`), wird ergänzt statt ersetzt |
| `--blatt NAME` | das erste | Arbeitsblatt in der Mappe |
| `--status STATUS` | alle | nur Anzeigen mit diesem Status |
| `--ohne-details` | aus | keine Anzeigentexte holen – schnell, aber Kontakt, Benefits und Gehalt bleiben leer und die Passung steht auf „zu wenig Angaben" |
| `--details-erneuern` | aus | zwischengespeicherte Texte neu abrufen |
| `--profil DATEI` | `bewerbung/profil.json` | Profil für die Passungsbewertung |
| `--ohne-passung` | aus | ohne Bewertung, auch wenn ein Profil vorliegt |
| `--ueberschreiben` | aus | auch bereits gefüllte Vorschlagsspalten erneuern |
| `--mit-aussortierten` | aus | Anzeigen behalten, deren Titel unter den Ausschluss fällt |

Vor jedem Schreiben entsteht `<name>.sicherung.xlsx` neben der Datei.

**Titel-Ausschluss.** Der Dedup-Schritt legt *jede* gesehene Anzeige in DynamoDB
an – auch die, die der Pipeline-Filter danach verwirft, sonst würde dieselbe
unpassende Anzeige jeden Poller-Lauf neu geholt. Der Export wendet deshalb
dieselbe Liste (`MATCH_AUSSCHLUSS`, Abschnitt 4) noch einmal auf den Titel an:
`senior`-, `lead`-, `praktikum`-Stellen usw. kommen nicht in die Tabelle, und
bereits vorhandene solche Zeilen im Status `GEFUNDEN` werden beim nächsten Lauf
entfernt. Alles ab `BEWORBEN` bleibt unangetastet. `--mit-aussortierten` schaltet
das ab.

Mit Profil ist die Tabelle **nach Passung sortiert** – beste Übereinstimmung
oben, innerhalb einer Stufe nach Punkten. Jeder Lauf ordnet die Zeilen neu; die
`Nr.` ist damit der aktuelle Rang. Handeinträge (Termine, Notizen) wandern über
die versteckte `Referenz`-Spalte mit ihrer Anzeige mit.

Eine Gehaltsschätzung aus dem Entgeltatlas gibt es hier nicht mehr: der Median
war für alle Anzeigen einer Berufsklasse derselbe und sagte nichts über die
konkrete Stelle. Für eine Einordnung fragt man `salary-check` gezielt.

### `trend` – Skill-Trend über das Archiv

```powershell
python -m tracker.main trend
python -m tracker.main trend --tage 90 --hochladen
```

| Schalter | Vorgabe | Bedeutung |
|----------|---------|-----------|
| `--tage N` | alles | nur die letzten N Tage auswerten |
| `--datei DATEI` | `dashboards/skill-trend.html` | Zieldatei |
| `--ohne-texte` | aus | ohne die zwischengespeicherten Anzeigentexte – schneller, aber gröber |
| `--hochladen` | aus | zusätzlich nach S3 legen und einen **7 Tage gültigen** Link ausgeben |
| `--profil DATEI` | `bewerbung/profil.json` | Profil für den Abgleich |
| `--ohne-passung` | aus | nur Marktzahlen, kein Abgleich |

---

## 3. `salary-check` – Gehalt einordnen

Aufruf aus `services/salary-check`, Modul `salary_check.main`. Braucht
keine Umgebungsvariablen, nur Netzzugriff.

```powershell
python -m salary_check.main --titel "Junior Data Engineer"
python -m salary_check.main --kldb 43413 --region deutschland
```

| Schalter | Bedeutung |
|----------|-----------|
| `--titel TITEL` | Stellenbezeichnung, wird auf einen KldB-Schlüssel abgebildet |
| `--kldb SCHLUESSEL` | Schlüssel direkt angeben (3 bis 5 Ziffern) |
| `--region hamburg\|deutschland` | Bezugsraum, Vorgabe `hamburg` |

`--titel` und `--kldb` schließen einander aus, eines von beiden ist Pflicht.

**KldB-Schlüssel**: vier Ziffern Berufsgruppe plus eine fünfte für das
Anforderungsniveau.

| Ziffer | Niveau | wird abgeleitet aus |
|--------|--------|---------------------|
| `1` | Helfer | – |
| `2` | Fachkraft | „junior", „einsteiger", „berufseinsteiger", „trainee" |
| `3` | Spezialist | ohne Hinweis im Titel |
| `4` | Experte | „senior", „lead", „principal", „architekt", „head of" |

Berufsgruppen: `4341` Softwareentwicklung (Vorgabe), `4321`
IT-Anwendungsberatung (bei „consultant", „berater", „sap", „servicenow",
„salesforce" im Titel).

---

## 4. Feste Begriffe

### Bewerbungsstatus

In dieser Reihenfolge, sie bestimmt auch die Sortierung:

| Status | in der Tabelle | Bedeutung |
|--------|----------------|-----------|
| `GEFUNDEN` | *(leer)* | vom `filter-dedup` angelegt, wird nach 180 Tagen vergessen |
| `BEWORBEN` | `Abgeschickt` | ab hier bleibt der Eintrag dauerhaft |
| `INTERVIEW` | `Interview` | |
| `ZUSAGE` | `Zusage` | abgeschlossen |
| `ABSAGE` | `Absage` | abgeschlossen, sortiert ans Ende |
| `UNINTERESSANT` | `Nicht interessant` | verschwindet aus der Tabelle, bleibt in DynamoDB |

Groß- und Kleinschreibung ist beim Setzen egal, ein unbekannter Wert
wird abgewiesen.

### Passungsstufen

| Stufe | ab | Bedeutung |
|-------|----|-----------|
| `A – Volltreffer` | 55 Punkte | deckt den Großteil der Anforderungen |
| `B – Naheliegend` | 35 Punkte | solide Schnittmenge, Lücken schließbar |
| `C – Randbereich` | darunter | wenig Überschneidung |
| `D – zu wenig Angaben` | – | weniger als 3 bekannte Begriffe in der Anzeige |

Die Punktzahl ist die **gedämpfte Deckung**: welcher Anteil dessen, was
die Anzeige verlangt, im Profil steht – mit einem Zuschlag von 5 im
Nenner. Ohne ihn belohnte die Formel wortkarge Anzeigen: vier von vier
genannten Begriffen ergäben glatte 100 und stünden über zwölf von
fünfzehn. Mit Dämpfung sind es 44 gegen 60, und die Rangfolge stimmt.

Begriffe im **Titel** zählen dreifach. Schwerpunkte gehen nicht in die
Zahl ein, sie tragen in der Trefferspalte einen `*`. Die Schwellen sind
gesetzt, nicht gemessen – `rueckblick` stellt sie gegen die Wirklichkeit.

### Homeoffice-Modell

Gelesen wird in dieser Rangfolge – eine Zahl der Schnittstelle schlägt
alles, danach der Anzeigentext, zuletzt die schwachen Ja/Nein-Felder:

| Text | woher |
|------|-------|
| `100 % remote` | `homeofficeprozent >= 100`, oder „100 % Homeoffice", „vollständig remote", „ortsunabhängig" im Text |
| `hybrid, N % Homeoffice` | `0 < homeofficeprozent < 100` |
| `hybrid, N Tage/Woche` | „2 Tage Homeoffice pro Woche" im Text |
| `hybrid, Umfang offen` | „hybrides Arbeitsmodell" im Text |
| `nach Vereinbarung` | `homeofficetyp = NACH_VEREINBARUNG` |
| `möglich, Umfang offen` | „mobiles Arbeiten", „Home-Office-Option", oder `homeofficemoeglich` |
| `vor Ort` | nur wenn die Anzeige es sagt: „keine Möglichkeit zum Homeoffice", „Präsenzpflicht" |
| *(leer)* | **keine Angabe** |

Der wichtigste Unterschied zur früheren Fassung: fehlt jede Angabe,
bleibt die Zelle **leer**. Vorher stand dort `vor Ort` – eine Behauptung,
die die Daten nicht hergaben, und der häufigste Grund für falsche Werte.
An 197 Anzeigen gemessen: vorher 223× `vor Ort`, jetzt 1× (ausdrücklich
so genannt), dafür 30× `100 % remote` und 28× `nach Vereinbarung`, die
vorher untergingen.

Ein beiläufiges „vor Ort" zählt nicht – das steht auch in „Sportangebote
direkt vor Ort" und „Termine beim Kunden vor Ort".

`NACH_VEREINBARUNG` gilt **nicht** als remote ([ADR 0006](adr/0006-bundesweite-remote-stellen.md)).

### Spalten der Bewerbungstabelle

17 Spalten, in dieser Reihenfolge: `Nr.`, `Passung`, `Punkte`, `Status`,
`Firma`, `Position`, `Link zur Ausschreibung`, `Standort`,
`Entfernung (km)`, `Benefits`, `Homeoffice-Modell`, `Gehalt`,
`Alter (Tage)`, `Treffer`, `Lücken`, `Kontakt`, `Quelle`. Ohne Profil
fallen `Passung`, `Punkte`, `Treffer` und `Lücken` weg. Dazu die
ausgeblendete Spalte `Referenz`, über die ein späterer Export seine
Zeilen wiederfindet.

Zwei Stufen bestimmen, was ein zweiter Export anfasst:

| Stufe | Spalten | Verhalten |
|-------|---------|-----------|
| automatisch | `Nr.`, `Passung`, `Punkte`, `Status`, `Treffer`, `Lücken`, `Firma`, `Position`, `Standort`, `Homeoffice-Modell`, `Alter (Tage)`, `Entfernung (km)`, `Link zur Ausschreibung`, `Quelle` | jedes Mal überschrieben |
| Vorschlag | `Gehalt`, `Benefits`, `Kontakt` | nur eingetragen, solange die Zelle leer ist |

**Handgepflegte Spalten gibt es nicht mehr.** Termine und Notizen von Hand
nachzutragen war Arbeit, die niemand macht; was wirklich gebraucht wird –
seit wann eine Bewerbung läuft – steht ohnehin in DynamoDB und beantwortet
`faellig`.

Zugeordnet wird über die **Überschrift**, nicht über die Spaltenposition –
umsortieren und eigene Spalten einfügen ist gefahrlos.

#### Die Statusspalte ist ein Auswahlfeld

`Status` ist die einzige Spalte, in die du selbst schreibst – per Klick,
nicht per Tippen:

| Auswahl | Wirkung |
|---------|---------|
| *(leer)* | noch nichts entschieden |
| `Abgeschickt` | rutscht nach oben zu den laufenden Bewerbungen |
| `Interview` | ebenso, und weiter nach oben |
| `Zusage` | ganz nach oben |
| `Absage` | ans Ende der Tabelle |
| `Nicht interessant` | **verschwindet beim nächsten Export** |

Der Export liest die Auswahl zurück nach DynamoDB, **bevor** er von dort
zurückschreibt – sonst überschriebe der Lauf die eigene Eingabe. Ein
Zellinhalt, den er nicht kennt, wird gemeldet und übergangen, nicht
geraten; Beschriftungen früherer Fassungen (`Beworben`, `Gefunden`)
werden weiterhin verstanden.

**Der Status überlebt jeden Schemawechsel.** Ändert sich der Spaltensatz,
räumt der Export die vorhandene Datei um, statt einen Neuaufbau zu
verlangen: Tracker-Spalten nehmen ihre Reihenfolge ein, eigene Spalten
wandern nach rechts, abgelegte fallen weg. Die Datei zu **löschen** ist
dagegen nie nötig und kostet jede Auswahl, die seit dem letzten Export
getroffen wurde – bis dahin steht sie nur in der Datei.

Umgekehrt gilt: ein Export gegen eine **veraltete Kopie** der Tabelle
dreht Entscheidungen zurück, denn die Tabelle ist für den Status die
Wahrheit. Mit einer Datei arbeiten, nicht mit mehreren.

Ausgeblendete Anzeigen bleiben in DynamoDB, damit dieselbe Stelle nicht
beim nächsten Lauf erneut auftaucht.

#### Gestaltung

Der Export gestaltet die Tabelle bei **jedem** Lauf, nicht nur beim
Anlegen – sonst wären die Zeilen nach jedem Export anders hoch:

* **einheitliche Zeilenhöhe.** Alle Zellen brechen um, und jede Zeile
  bekommt die Höhe, die die vollste Zelle der ganzen Tabelle braucht.
  Nichts wird abgeschnitten, und das Raster bleibt ruhig. Gedeckelt bei
  acht Textzeilen, damit eine einzelne ausufernde Zelle nicht alles auf
  Handtuchhöhe zieht.
* **Farbe nach Passung und Status** – als bedingte Formatierung, nicht
  als feste Füllung: wählst du im Auswahlfeld einen anderen Status,
  färbt Excel sofort um, ohne dass ein Export dazwischen muss.
* **Erste Spalten stehen fest** (bis einschließlich `Position`), damit
  beim Blättern nach rechts sichtbar bleibt, um welche Anzeige es geht.
* **Autofilter über den ganzen Bereich**, nicht nur die Kopfzeile –
  sonst zeigt Excel die Pfeile, filtert aber nichts.
* Zahlen mittig mit festem Format, Text linksbündig und oben.

Eigene Spalten bleiben erhalten; vermessen und gefärbt werden nur die
bekannten.

#### Sortierung

Drei Blöcke, damit von oben nach unten steht, worum man sich kümmern muss:

1. **laufende Bewerbungen** – Zusage vor Interview vor Abgeschickt,
2. **Unberührtes** nach Passung, beste Übereinstimmung oben,
3. **Absagen**.

Jeder Lauf ordnet neu; die `Nr.` ist damit der aktuelle Rang. Sortiert
wird die volle Zeilenbreite, fremde Spalten wandern mit. Zeilenbezogene
Handformatierung und Formeln mit Zeilenbezug überstehen das nicht –
dafür liegt die Sicherung daneben.

`Quelle` nennt die Börse, die die Anzeige gemeldet hat; `Link zur
Ausschreibung` führt entsprechend in die Jobbörse der Arbeitsagentur oder
direkt zum Portal. `Kontakt` fasst Ansprechpartner und E-Mail/Telefon
zusammen, `Gehalt` nimmt eine Angabe aus dem Anzeigentext
(Betrag, Spanne oder Entgeltgruppe) – beides heuristisch aus dem Text
gezogen und deshalb nur Vorschlag. `Entfernung (km)` kommt von der
Bundesagentur mit; bei den übrigen Quellen wird sie als Luftlinie aus
dem Ortsnamen gerechnet, soweit die Stadt in
[`gemeinsam/entfernung.py`](../services/gemeinsam/gemeinsam/entfernung.py)
steht.

---

## 5. Das Profil bearbeiten

`bewerbung/profil.json`, von Hand änderbar:

```json
{
  "quellen": ["Lebenslauf.pdf"],
  "faehigkeiten": { "Spring": 6, "Java": 5, "Jira": 4 },
  "eigene": ["Kafka", "AWS", "Terraform"],
  "ausgeschlossen": ["Oracle"]
}
```

| Feld | Bedeutung |
|------|-----------|
| `faehigkeiten` | aus den Unterlagen gelesen, mit Häufigkeit. Wird bei jedem `profil`-Lauf neu geschrieben |
| `eigene` | von Hand ergänzt. Zählt als **Schwerpunkt** und überlebt ein erneutes Einlesen |
| `ausgeschlossen` | von Hand gestrichen, fällt aus beiden Mengen |
| `quellen` | welche Dateien gelesen wurden |

**Schwerpunkt** ist, was mindestens **3-mal** in den Unterlagen steht oder
in `eigene` eingetragen ist.

Ein Tippfehler in `eigene` oder `ausgeschlossen` wird beim Laden als
Warnung gemeldet. Gültig sind genau diese Bezeichnungen:

| Kategorie | Bezeichnungen |
|-----------|---------------|
| Programmiersprachen | `Java`, `Python`, `JavaScript`, `TypeScript`, `SQL`, `Kotlin`, `Scala`, `Go`, `Rust`, `C#`, `C++`, `PHP`, `Bash`, `R` |
| Frameworks | `Spring`, `React`, `Angular`, `Vue`, `Node.js`, `Django`, `FastAPI`, `Hibernate`, `Maven`, `Gradle`, `REST-APIs`, `GraphQL`, `Microservices` |
| Daten | `Kafka`, `Spark`, `Airflow`, `dbt`, `ETL`, `Data Warehouse`, `BigQuery`, `Snowflake`, `Databricks`, `Pandas`, `Machine Learning`, `Power BI`, `Tableau` |
| Cloud und Betrieb | `AWS`, `Azure`, `GCP`, `Docker`, `Kubernetes`, `Terraform`, `CI/CD`, `GitLab`, `GitHub`, `Jenkins`, `Git`, `Linux`, `Monitoring`, `Serverless` |
| Datenbanken | `PostgreSQL`, `MySQL`, `Oracle`, `MongoDB`, `Redis`, `DynamoDB`, `Elasticsearch` |
| Testen | `JUnit`, `Selenium`, `Playwright`, `Testautomatisierung`, `Unit-Tests`, `Code Review` |
| Methoden | `Scrum`, `Agile Arbeitsweise`, `DevOps`, `Jira`, `Softwarearchitektur`, `Anforderungsanalyse`, `Datenschutz` |
| Sprachen | `Deutsch`, `Englisch` |

Neue Begriffe kommen in
[`services/gemeinsam/gemeinsam/faehigkeiten.py`](../services/gemeinsam/gemeinsam/faehigkeiten.py)
dazu.

### Benefits

Was die Benefits-Spalte im Anzeigentext erkennt – festes Verzeichnis in
[`services/tracker/tracker/benefits.py`](../services/tracker/tracker/benefits.py):

`Unbefristet`, `Tarifvertrag`, `Gleitzeit`, `Teilzeit möglich`,
`30+ Tage Urlaub`, `Betriebliche Altersvorsorge`,
`Vermögenswirksame Leistungen`, `Bonus / Sonderzahlung`,
`Jobticket / ÖPNV`, `Jobrad / Bikeleasing`, `Firmenwagen`,
`Weiterbildung`, `Sport / Gesundheit`, `Kantine / Verpflegung`,
`Kinderbetreuung`, `Mitarbeiterrabatte`, `Sabbatical`, `Firmenevents`,
`Parkplatz`, `Umzugshilfe`

---

## 6. Umgebungsvariablen

### Lokal (tracker, salary-check)

| Variable | Vorgabe | Bedeutung |
|----------|---------|-----------|
| `DYNAMODB_TABLE_SEEN_JOBS` | – | Tabelle der gesehenen Anzeigen. Pflicht außer bei `profil` |
| `S3_BUCKET_RAW_ARCHIVE` | – | Archiv-Bucket. Pflicht für `export` und `trend` |
| `JOBRADAR_PROFIL` | `bewerbung/profil.json` | anderer Ablageort des Profils |
| `AWS_DEFAULT_REGION` | – | `eu-central-1` |

### Poller (Suche)

| Variable | Vorgabe | Bedeutung |
|----------|---------|-----------|
| `JOBSUCHE_WAS` | `Data Engineer` | Suchbegriffe, mit Komma getrennt |
| `JOBSUCHE_WO` | `Hamburg` | Suchort |
| `JOBSUCHE_UMKREIS_KM` | `30` | Umkreis |
| `JOBSUCHE_VEROEFFENTLICHT_SEIT_TAGEN` | `7` | **nur 0, 1, 7, 14, 28** – jeder andere Wert wird von der API stillschweigend verworfen ([ADR 0001](adr/0001-datenquelle-jobsuche-api.md)) |
| `JOBSUCHE_SEITENGROESSE` | `50` | Treffer je Seite |
| `JOBSUCHE_REMOTE_BUNDESWEIT` | `true` | zweiter Durchgang ohne Ortsbindung |
| `JOBSUCHE_REMOTE_MIN_PROZENT` | `100` | Mindest-Homeoffice-Anteil in diesem Durchgang |
| `JOBSUCHE_BASE_URL` | REST-Endpunkt der Jobsuche | |
| `JOBSUCHE_API_KEY` | `jobboerse-jobsuche` | öffentlich bekannte clientId, kein Geheimnis |
| `POLLER_QUELLEN` | `arbeitsagentur,arbeitnow,adzuna` | welche Börsen abgefragt werden, siehe unten |
| `ADZUNA_APP_ID` | leer | Zugangsdaten von developer.adzuna.com |
| `ADZUNA_APP_KEY` | leer | fehlt eines von beiden, bleibt Adzuna still |

### Stellenbörsen

Je Börse eine Datei in
[`services/poller/poller/quellen/`](../services/poller/poller/quellen/).
Alle übersetzen ins Format der Jobsuche-API, damit flussabwärts nichts
unterschieden werden muss.

| Name | Bestand | Zugangsdaten | Anzeigentext |
|------|---------|--------------|--------------|
| `arbeitsagentur` | Hamburg + bundesweit remote | – | einzeln nachgeladen |
| `arbeitnow` | Deutschland | – | liegt bei |
| `adzuna` | Deutschland, Aggregator | `ADZUNA_APP_ID`/`_KEY` | Auszug liegt bei |
| `remotive` | weltweit remote | – | liegt bei |
| `remoteok` | weltweit remote | – | liegt bei |
| `jobicy` | remote, Region Deutschland | – | liegt bei |

`JOBSUCHE_WAS`, `JOBSUCHE_WO` und `JOBSUCHE_VEROEFFENTLICHT_SEIT_TAGEN`
gelten für **alle** Quellen — bei der Bundesagentur ist jeder Begriff eine
eigene Suche, bei den übrigen ein Filter auf den Titel. Mehrere Begriffe
lohnen sich deshalb doppelt; voreingestellt sind:

```
Data Engineer, Softwareentwickler, Software Engineer, Developer, Java
```

Der Titelfilter arbeitet auf zwei Wegen:

* Nennt ein Begriff genau eine Fähigkeit aus
  [`faehigkeiten.py`](../services/gemeinsam/gemeinsam/faehigkeiten.py),
  gilt deren geprüftes Muster. Bei kurzen Namen ist das entscheidend:
  **`Java` trifft nicht `JavaScript`**.
* Sonst müssen **alle Wörter** des Begriffs als Teilzeichenkette
  vorkommen. Auf Teilzeichenketten, weil deutsche Titel zusammenschreiben:
  `Softwareentwickler` wird gefunden, `Data Engineer` findet auch
  `Data Platform Engineer` — aber keinen Vertriebsposten.

Ändern lässt sich das je Lauf oder dauerhaft in `infra/terraform.tfvars`
(`suchbegriffe`):

```powershell
$env:JOBSUCHE_WAS = "Data Engineer,Java,Kotlin,Developer"
```

Fällt eine Börse aus oder bremst sie mit HTTP 429, überspringt der Poller
sie mit einer Warnung und macht mit den übrigen weiter.

**Nicht dabei sind LinkedIn, Indeed, StepStone und get-in-it.** Ihre
Nutzungsbedingungen untersagen automatisiertes Auslesen, und sie setzen
das auch technisch durch. Eine Integration wäre ein absehbar gesperrter
Poller.

### Kafka (poller, filter-dedup, notifier)

| Variable | Vorgabe | Bedeutung |
|----------|---------|-----------|
| `KAFKA_BOOTSTRAP_SERVERS` | – | Pflicht. **DNS-Name**, nicht IP – sonst schlägt die Zertifikatsprüfung fehl |
| `KAFKA_TOPIC_RAW` | `jobs.raw` | |
| `KAFKA_TOPIC_MATCHED` | `jobs.matched` | |
| `KAFKA_GROUP_ID` | `filter-dedup` bzw. `notifier` | anderer Name liest den Strom von vorn |
| `KAFKA_SASL_USERNAME` | `jobradar` | |
| `KAFKA_SASL_PASSWORD` | – | für lokale Läufe |
| `KAFKA_PASSWORD_SSM_PARAMETER` | – | Alternative: Name des SSM-Parameters |
| `KAFKA_CA_CERT_PATH` | – | Pfad zum CA-Zertifikat |
| `KAFKA_CA_CERT_SSM_PARAMETER` | – | Alternative für die Lambda, schreibt nach `/tmp` |

Passwort und Zertifikat: entweder direkt oder über SSM, eines von beidem
muss gesetzt sein.

### filter-dedup

| Variable | Vorgabe | Bedeutung |
|----------|---------|-----------|
| `MATCH_AUSSCHLUSS` | siehe unten | Titelbegriffe, die aussortieren |
| `MATCH_ARBEITGEBER_AUSSCHLUSS` | `ntt data` | Firmennamen, die aussortieren |
| `MATCH_PFLICHT` | leer | mindestens einer muss vorkommen. Leer = keine Einschränkung |
| `DEDUP_AUFBEWAHRUNG_TAGE` | `180` | Frist für Anzeigen im Status `GEFUNDEN` |
| `JOBRADAR_PROFIL` | leer | Profil für die Bewertung. Leer = keine Bewertung |
| `FILTER_DETAILS` | `true` | Anzeigentexte holen. `false` spart Abrufe, kostet die Bewertung |

Voreingestellter Ausschluss:

```
praktikum, werkstudent, ausbildung, minijob, aushilfe, schulpraktikum,
senior, sr, lead, teamlead, leiter, teamleiter, principal, staff,
head of, c++, embedded, sap
```

Voreingestellte Arbeitgeber: `ntt data`. Diese Liste prüft den
**Firmennamen** statt des Titels — ein Eintrag deckt alle Firmierungen
ab, die so beginnen (`NTT DATA Deutschland SE` und `NTT DATA Business
Solutions Global Managed Services GmbH` mit einem Eintrag).

Verglichen wird auf den **Wortanfang**: `sr` trifft „Sr." aber nicht
„I**sr**ael"; `praktikum` erfasst weiterhin „Praktikumsstelle". Deshalb
stehen `lead` und `teamlead` beide auf der Liste. Bewusst nicht dabei:
`manager` – das würde „Junior Customer Success Manager" aussortieren.

Liste und Vergleich liegen in
[`services/gemeinsam/gemeinsam/ausschluss.py`](../services/gemeinsam/gemeinsam/ausschluss.py).
`tracker liste` und `tracker export` lesen **dieselbe** Variable `MATCH_AUSSCHLUSS`
und wenden sie auf den Anzeigentitel an – was die Mail verschweigt, soll auch
nicht in die Tabelle. Setzt du sie lokal, muss sie zum Wert auf der Instanz
passen.

### notifier

| Variable | Vorgabe | Bedeutung |
|----------|---------|-----------|
| `SES_SENDER_ADDRESS` | – | Pflicht, in SES bestätigt |
| `SES_RECIPIENT_ADDRESS` | – | Pflicht |
| `NOTIFIER_MAX_STAPEL` | `25` | ab so vielen Anzeigen geht die Mail sofort raus |
| `NOTIFIER_WARTEZEIT_SEKUNDEN` | `60` | sonst nach so viel Ruhe |

---

## 7. Betrieb

```powershell
# Dienste beobachten
ssh ec2-user@$(terraform -chdir=infra output -raw kafka_public_dns)
sudo journalctl -u jobradar-filter-dedup -f
sudo journalctl -u jobradar-notifier -f
systemctl is-active jobradar-filter-dedup jobradar-notifier

# Poller von Hand auslösen. Der Name ist "<project_name>-poller",
# voreingestellt also jobradar-poller.
aws lambda invoke --function-name $(terraform -chdir=infra output -raw poller_function_name) antwort.json
aws logs tail $(terraform -chdir=infra output -raw poller_log_group) --since 10m --format short

# nach einer Codeänderung
& "C:\Program Files\Git\bin\bash.exe" scripts/deploy-consumers.sh  # Consumer
python services/poller/build.py; if ($?) { terraform -chdir=infra apply }   # Poller

# Instanz stoppen und starten
aws ec2 stop-instances  --instance-ids $(terraform -chdir=infra output -raw kafka_instance_id)
aws ec2 start-instances --instance-ids $(terraform -chdir=infra output -raw kafka_instance_id)
```

Nach einem Start ändert sich die öffentliche Adresse. Einmal
`terraform -chdir=infra apply` zieht sie in die Lambda-Konfiguration
nach, `bash scripts/deploy-consumers.sh` in die der Consumer.

Betriebssystem-Image bewusst wechseln:

```powershell
terraform -chdir=infra apply -replace=module.ec2_kafka.aws_instance.kafka
```

### Tests

Je Service einzeln – jeder hat eine eigene `pytest.ini`, ein gemeinsamer
Aufruf über mehrere Verzeichnisse schlägt fehl:

```powershell
python -m pytest services/gemeinsam
python -m pytest services/poller
python -m pytest services/filter-dedup
python -m pytest services/notifier
python -m pytest services/salary-check
python -m pytest services/tracker
```

Alle laufen ohne Netzzugriff und ohne AWS.

---

## 8. Was nicht ins Repo gehört

In `.gitignore`, doppelt abgesichert über Verzeichnis **und** Dateinamen:

| Muster | Inhalt |
|--------|--------|
| `bewerbung/` | Lebenslauf, Zeugnisse, `profil.json` |
| `*.pdf`, `*.docx`, `Lebenslauf*`, `Zeugnis*`, `CV.*` | Unterlagen, wo auch immer sie liegen |
| `dashboards/*.html` | der erzeugte Skill-Trend, enthält die eigenen Lücken |
| `*.xlsx`, `*.xls` | die ausgefüllte Bewerbungstabelle |
| `*.tfvars`, `*.tfstate*`, `.env`, `*.pem` | Zugangsdaten und lokaler Zustand |

Prüfen, ob eine Datei wirklich ignoriert wird:

```powershell
git check-ignore -v bewerbung/profil.json
```

Ein PDF trotzdem bewusst einchecken: `git add -f <datei>`.

---

## 9. Wo etwas herkommt

| Schnittstelle | Wofür | Kosten |
|---------------|-------|--------|
| `rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs` | Trefferliste | – |
| `.../pc/v4/jobdetails/{base64(referenznummer)}` | Anzeigentext, Kontakt, Vergütung | – |
| `rest.arbeitsagentur.de/infosysbub/entgeltatlas/pc/v1/entgelte/{KldB}` | Gehaltsmedian | – |

Beide sind **inoffiziell**: öffentlich erreichbar, aber ohne Vertrag und
ohne Zusage. Pfade und Feldnamen ändern sich ohne Ankündigung – während
der Entwicklung bereits zweimal. Deshalb wird defensiv abgefragt, jeder
Anzeigentext nur **einmal je Anzeige** geholt und im Archiv unter
`detail/` zwischengespeichert.

Kein Sprachmodell im Spiel: Passung, Benefits, Kontaktdaten und
Skill-Trend entstehen ausschließlich durch Feldzuordnung und
Mustersuche. Es fallen keine Kosten je Anzeige an.
