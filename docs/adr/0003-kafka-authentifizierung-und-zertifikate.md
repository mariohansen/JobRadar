# ADR 0003: SASL/SCRAM und eigene CA fuer den Broker

Datum: 2026-08-31
Status: akzeptiert

## Kontext

Aus ADR 0002 folgt ein oeffentlich erreichbarer Broker. Die
Authentifizierung ist damit die einzige wirksame Schranke - die Security
Group kann sie nicht ersetzen, weil die Lambda ausserhalb der VPC laeuft
und aus wechselnden AWS-IP-Bereichen kommt.

## Entscheidungen

### SCRAM-SHA-512 statt PLAIN

Bei SASL/PLAIN liegt das Passwort im Klartext in der Broker-Konfiguration
und geht bei jeder Anmeldung ueber die Leitung - abgesichert nur durch
die TLS-Schicht darunter. SCRAM ist ein Challenge-Response-Verfahren: der
Broker speichert lediglich einen abgeleiteten Wert, das Passwort selbst
verlaesst den Client nie.

Die SCRAM-Anmeldedaten liegen im KRaft-Metadatenlog, nicht in einer
Datei. Angelegt werden sie ueber den internen PLAINTEXT-Listener, der nur
innerhalb des Containers erreichbar ist. Das loest ein Henne-Ei-Problem:
ohne Benutzer keine Anmeldung, ohne Anmeldung kein Benutzer.

### Eigene CA mit Wildcard-Zertifikat

Ohne eigene Domain kommt kein oeffentlich anerkanntes Zertifikat in
Frage; Let's Encrypt stellt fuer `*.compute.amazonaws.com` keine aus.
Also eine eigene CA, deren Zertifikat die Clients als Vertrauensanker
mitbekommen.

Das Broker-Zertifikat traegt als SAN `*.<region>.compute.amazonaws.com`.
Der oeffentliche DNS-Name der Instanz aendert sich bei jedem Stop/Start,
folgt aber immer diesem Muster. Dadurch bleibt die Hostname-Pruefung im
Client aktiv. Die uebliche Abkuerzung waere,
`ssl.endpoint.identification.algorithm` leer zu setzen und damit die
Pruefung ganz abzuschalten - das faellt hier weg.

Aus demselben Grund lautet `bootstrap.servers` auf den DNS-Namen und
nicht auf die IP: gegen eine IP-Adresse schlaegt die Pruefung fehl.

### SSM Parameter Store statt Secrets Manager

Standard-Parameter sind kostenlos, SecureString verschluesselt mit dem
AWS-verwalteten Schluessel `aws/ssm` ohne Zusatzkosten. Secrets Manager
koennte automatisch rotieren, kostet aber 0,40 USD pro Secret und Monat -
fuer eine Rotation, die dieses Projekt nicht nutzt.

Nicht in Frage kam, die Werte in `user_data` zu schreiben: dessen Inhalt
ist ueber den Metadatendienst fuer jeden Prozess auf der Instanz im
Klartext lesbar.

### Konfiguration bei jedem Boot statt einmalig

`user_data` laeuft nur beim allerersten Boot. Da sich die oeffentliche
Adresse bei jedem Stop/Start aendert und in
`KAFKA_ADVERTISED_LISTENERS` stehen muss, rendert eine systemd-Einheit
die Konfiguration bei jedem Start neu und holt dabei auch die
Zertifikate frisch aus SSM.

## Konsequenzen

Die privaten Schluessel von CA und Broker liegen im Terraform-State. Der
ist gitignored, aber damit eine Datei, die wie ein Schluesselbund zu
behandeln ist. Ein Remote-Backend mit Verschluesselung waere der
naechste Schritt, sobald das Projekt nicht mehr nur auf einem Rechner
laeuft.

Beim Anlegen des SCRAM-Benutzers steht das Passwort kurzzeitig in der
Prozessliste der Instanz. Auf einer Einzelnutzer-Instanz ist das
vertretbar; in einer Mehrbenutzerumgebung waere es das nicht.

Zertifikate laufen nach einem Jahr ab. Danach genuegt ein erneutes
`terraform apply` - die Instanz zieht die neuen Dateien beim naechsten
Boot aus SSM.

## Stolpersteine beim Aufbau

Drei Dinge, an denen der Broker beim ersten Anlauf gescheitert ist. Alle
drei sind im Code kommentiert, hier der Zusammenhang:

**JAAS ist auch bei SCRAM Pflicht.** Die Annahme, dass die im
KRaft-Metadatenlog gespeicherten Anmeldedaten genuegen, ist falsch. Kafka
verlangt fuer jeden SASL-Listener einen Login-Modul-Eintrag und bricht
sonst ab mit "Could not find a 'KafkaServer' entry in the JAAS
configuration". Der Eintrag enthaelt dabei selbst keine Benutzerdaten -
er deklariert nur `ScramLoginModule`.

**Der Broker laeuft im Container nicht als root.** Das Image
`apache/kafka` startet als `appuser` mit UID 1000. Ein Verzeichnis mit
`0700 root` fuer die Zertifikate sperrt damit den Broker aus. Geloest
ueber `chown 1000:1000` statt ueber weichere Dateirechte - die Dateien
bleiben `0600`.

**Der tls-Provider liefert PKCS#1, Java erwartet PKCS#8.**
`tls_private_key.private_key_pem` erzeugt bei RSA einen Block mit dem
Kopf `BEGIN RSA PRIVATE KEY`. Java kann den nicht lesen und meldet
`algid parse error, not a sequence`. Das Attribut
`private_key_pem_pkcs8` liefert dasselbe Material im erwarteten Format.
