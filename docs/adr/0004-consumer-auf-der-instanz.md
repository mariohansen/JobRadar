# ADR 0004: Consumer laufen auf der Kafka-Instanz

Datum: 2026-08-31
Status: akzeptiert

## Kontext

filter-dedup und notifier sind Kafka-Consumer: sie warten auf
Nachrichten, statt zu festen Zeiten zu laufen wie der Poller. Fuer diese
Betriebsart gibt es zwei Wege.

## Entscheidung

Beide laufen als systemd-Dienste auf derselben EC2-Instanz wie der
Broker.

Verworfen wurde das **Lambda Event Source Mapping** fuer selbst
gehostetes Kafka. Es waere architektonisch stimmiger - dieselbe
Betriebsart wie beim Poller, keine Prozesse zu verwalten. Dahinter
steht aber ein von AWS betriebener Poller, der den Broker dauerhaft
abfragt und dafuer durchgehend abgerechnet wird. Fuer eine Pipeline mit
rund vierzig Anzeigen am Tag entstuenden so laufende Kosten fuer eine
Verbindung, die fast immer im Leerlauf ist.

Auf der Instanz laufen die Consumer dagegen auf Kapazitaet, die ohnehin
bezahlt ist, und erreichen den Broker ueber localhost.

## Konsequenzen

Der Arbeitsspeicher wird knapp. Die Instanz hat 916 MB, davon
beansprucht die Kafka-JVM den groessten Teil. Beide Dienste sind deshalb
per `MemoryMax=200M` begrenzt, damit ein aus dem Ruder laufender
Consumer nicht den Broker verdraengt.

Werden die Consumer gestoppt oder die Instanz heruntergefahren, sammeln
sich die Nachrichten im Topic an und werden beim naechsten Start
nachgeholt. Die Offsets werden erst nach erfolgreicher Verarbeitung
bestaetigt, sodass dabei nichts verloren geht.

Ausgerollt wird nicht ueber Terraform, sondern ueber
`scripts/deploy-consumers.sh`. Anwendungscode ueber `user_data`
auszuliefern wuerde die Instanz bei jeder Codeaenderung ersetzen -
Terraform bleibt fuer die Infrastruktur zustaendig, das Skript fuer den
Code darauf.

## Nachtrag: Python-Version

Amazon Linux 2023 liefert python3.9 als Standard. boto3 warnt dort
bereits vor dem Auslaufen des Supports, und die Poller-Lambda laeuft auf
3.13. Das Deploy-Skript installiert deshalb python3.13 und baut die
virtuelle Umgebung damit - eine einheitliche Version erspart Fehler, die
nur auf einer der beiden Seiten auftreten.
