"""Notifier.

Liest jobs.matched, sammelt die Anzeigen zu einem Stapel und verschickt
sie gebuendelt. Der Stapel geht raus, sobald er voll ist oder eine Weile
nichts Neues mehr eingetroffen ist.
"""
from __future__ import annotations

import json
import logging
import signal
import sys
import time
from types import FrameType
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from confluent_kafka import Consumer, KafkaError

from .config import ConfigError, KafkaConfig, MailConfig
from .sender import Versand

log = logging.getLogger(__name__)

_laeuft = True


def _beenden(signum: int, rahmen: FrameType | None) -> None:
    global _laeuft
    log.info("Signal %s empfangen, sende den angefangenen Stapel noch", signum)
    _laeuft = False


def _warte(sekunden: int) -> None:
    """Pause, die auf ein Stoppsignal reagiert.

    Ein einfaches sleep wuerde systemd beim Herunterfahren bis zum
    Zeitlimit blockieren.
    """
    ende = time.monotonic() + sekunden
    while _laeuft and time.monotonic() < ende:
        time.sleep(1)


def baue_consumer(config: KafkaConfig) -> Consumer:
    return Consumer(
        {
            "bootstrap.servers": config.bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "SCRAM-SHA-512",
            "sasl.username": config.sasl_username,
            "sasl.password": config.sasl_password,
            "ssl.ca.location": config.ca_cert_path,
            "ssl.endpoint.identification.algorithm": "https",
            "group.id": config.gruppe,
            "auto.offset.reset": "earliest",
            # Erst bestaetigen, wenn die Mail tatsaechlich raus ist.
            # Andernfalls koennte ein Absturz zwischen Lesen und Versand
            # Anzeigen verschlucken.
            "enable.auto.commit": False,
        }
    )


def stapel_faellig(
    anzahl: int, letzte_nachricht: float, mail_config: MailConfig, jetzt: float
) -> bool:
    """Ist der gesammelte Stapel reif zum Versand?"""
    if anzahl == 0:
        return False
    if anzahl >= mail_config.max_stapel:
        return True
    return (jetzt - letzte_nachricht) >= mail_config.wartezeit_sekunden


def run() -> int:
    kafka_config = KafkaConfig.from_env()
    mail_config = MailConfig.from_env()

    versand = Versand(mail_config.absender, mail_config.empfaenger)
    consumer = baue_consumer(kafka_config)
    consumer.subscribe([kafka_config.topic_matched])
    log.info("Lese %s als Gruppe %s", kafka_config.topic_matched, kafka_config.gruppe)

    stapel: list[dict[str, Any]] = []
    letzte_nachricht = time.monotonic()
    gesendet = 0

    def versende() -> None:
        nonlocal stapel, gesendet
        if not stapel:
            return

        try:
            kennung = versand.sende(stapel)
        except (ClientError, BotoCoreError) as exc:
            # Haeufigster Fall: die Adresse ist in SES noch nicht
            # bestaetigt. Das ist ein Zustand, kein Programmfehler -
            # abstuerzen und neu starten wuerde nur die Logs fluten.
            # Der Stapel bleibt liegen, die Offsets unbestaetigt; damit
            # geht nichts verloren und der naechste Anlauf versucht es
            # erneut.
            log.error("Versand fehlgeschlagen, spaeterer Versuch: %s", exc)
            _warte(mail_config.wartezeit_sekunden)
            return

        log.info("%s Anzeigen verschickt, MessageId %s", len(stapel), kennung)
        gesendet += len(stapel)
        # Offsets erst jetzt bestaetigen - die Mail ist raus.
        consumer.commit(asynchronous=False)
        stapel = []

    try:
        while _laeuft:
            nachricht = consumer.poll(timeout=1.0)

            if nachricht is not None and not nachricht.error():
                stapel.append(json.loads(nachricht.value()))
                letzte_nachricht = time.monotonic()
            elif nachricht is not None and nachricht.error():
                if nachricht.error().code() != KafkaError._PARTITION_EOF:
                    log.error("Kafka-Fehler: %s", nachricht.error())

            if stapel_faellig(len(stapel), letzte_nachricht, mail_config, time.monotonic()):
                versende()
    finally:
        # Was noch im Puffer liegt, geht beim Herunterfahren raus.
        try:
            versende()
        finally:
            consumer.close()
        log.info("Beendet. Insgesamt %s Anzeigen verschickt", gesendet)

    return gesendet


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )
    signal.signal(signal.SIGTERM, _beenden)
    signal.signal(signal.SIGINT, _beenden)

    try:
        run()
    except ConfigError as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
