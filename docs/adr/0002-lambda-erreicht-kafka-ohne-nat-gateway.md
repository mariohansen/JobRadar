# ADR 0002: Poller erreicht Kafka ohne NAT Gateway

Datum: 2026-08-31
Status: akzeptiert

## Kontext

Der Poller laeuft als Lambda und soll nach Kafka publishen, das auf einer
EC2-Instanz liegt. Dabei kollidieren zwei Anforderungen:

- Die Lambda braucht Internetzugang, um die Jobsuche-API der BA abzufragen.
- Die Lambda braucht Zugriff auf den Kafka-Broker.

Eine Lambda ohne VPC-Anbindung hat Internetzugang, aber keine Route ins
VPC. Haengt man sie in ein Subnetz, kehrt sich das um: der Broker ist
erreichbar, das Internet nicht mehr. Lambda-ENIs bekommen keine oeffentliche
IP, auch nicht in einem Public Subnet - der uebliche Ausweg ist ein
NAT Gateway.

## Entscheidung

Die Lambda bleibt ausserhalb der VPC. Der Kafka-Broker bekommt eine
oeffentliche IP und wird ueber SASL_SSL authentifiziert statt ueber
Netzwerkabschottung.

Verworfen wurden:

- **NAT Gateway.** Rund 35-40 USD pro Monat, laufend, unabhaengig von der
  Nutzung. Nicht Free Tier, und damit unvereinbar mit dem Budget dieses
  Projekts.
- **Bridge ueber SQS.** Sicherheitstechnisch sauberer, weil der Broker
  privat bliebe, aber Kafka waere nicht mehr die erste Station der
  Pipeline. Bleibt der Ausweichplan, falls sich der oeffentliche Broker
  als zu heikel erweist.
- **Poller als systemd-Timer auf der EC2.** Kostenlos und trivial, faellt
  aber hinter den Anspruch zurueck, Lambda und EventBridge tatsaechlich zu
  lernen.

## Konsequenzen

Der Broker ist aus dem Internet erreichbar und wird entsprechend gescannt.
Daraus folgt zwingend:

- Kein `PLAINTEXT`-Listener nach aussen. SASL_SSL ist Pflicht, nicht
  optional, und muss stehen, bevor der Broker das erste Mal oeffentlich
  hochkommt.
- Die Security Group oeffnet ausschliesslich den Kafka-Listener-Port.
  SSH-Zugriff nur von der eigenen IP.
- Weil Lambda aus wechselnden AWS-IP-Bereichen kommt, laesst sich der
  Zugriff nicht per Security Group auf eine feste Adresse eingrenzen. Die
  Authentifizierung ist damit die einzige wirksame Schranke - ein
  schwaches Broker-Passwort waere hier gleichbedeutend mit einem offenen
  Broker.

Oeffentliche IPv4-Adressen kosten seit 2024 rund 3,60 USD pro Monat; im
Free Tier neuer Accounts ist ein solches Kontingent zunaechst enthalten.
