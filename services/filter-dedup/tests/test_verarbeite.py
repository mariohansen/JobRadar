"""Test der Reihenfolge im Consumer.

Geprueft wird, was mit einer Anzeige geschieht und in welcher Reihenfolge
die Stufen greifen: archivieren, Kennung pruefen, Inhalt pruefen, filtern.
"""
from filter_dedup.config import FilterConfig
from filter_dedup.main import verarbeite


class FakeArchiv:
    def __init__(self):
        self.abgelegt = []

    def ablegen(self, referenznummer, job):
        self.abgelegt.append(referenznummer)


class FakeDedup:
    def __init__(self):
        self.kennungen = set()
        self.inhalte = set()

    def ist_neu(self, referenznummer, titel=""):
        if referenznummer in self.kennungen:
            return False
        self.kennungen.add(referenznummer)
        return True

    def ist_inhaltlich_neu(self, schluessel, referenznummer):
        if schluessel in self.inhalte:
            return False
        self.inhalte.add(schluessel)
        return True


class FakeProducer:
    def __init__(self):
        self.gesendet = []

    def produce(self, topic, key, value):
        self.gesendet.append(key.decode("utf-8"))


def konfiguration(ausschluss=(), pflicht=()):
    return FilterConfig(
        tabelle="t",
        bucket="b",
        profil_pfad="",
        mit_details=False,
        ausschluss=ausschluss,
        pflicht=pflicht,
        aufbewahrung_tage=180,
    )


def stelle(referenz, firma="Beispiel GmbH", titel="Data Engineer (m/w/d)"):
    return {
        "referenznummer": referenz,
        "firma": firma,
        "stellenangebotsTitel": titel,
        "stellenlokationen": [{"adresse": {"ort": "Hamburg"}}],
    }


def lauf(jobs, ausschluss=()):
    archiv, dedup, producer = FakeArchiv(), FakeDedup(), FakeProducer()
    ergebnisse = [
        verarbeite(
            job,
            job["referenznummer"],
            archiv,
            dedup,
            konfiguration(ausschluss),
            producer,
            "jobs.matched",
        )
        for job in jobs
    ]
    return ergebnisse, archiv, producer


def test_neue_anzeige_wird_weitergereicht():
    ergebnisse, _, producer = lauf([stelle("10001-1-S")])

    assert ergebnisse == ["weitergereicht"]
    assert producer.gesendet == ["10001-1-S"]


def test_gleiche_kennung_gilt_als_bekannt():
    ergebnisse, _, _ = lauf([stelle("10001-1-S"), stelle("10001-1-S")])

    assert ergebnisse == ["weitergereicht", "bekannt"]


def test_gleiche_stelle_von_anderer_quelle_gilt_als_doppelt():
    """Andere Referenznummer, gleicher Inhalt - nur einmal melden."""
    ergebnisse, _, producer = lauf(
        [
            stelle("10001-1-S"),
            stelle("arbeitnow:data-engineer", firma="Beispiel GmbH & Co. KG",
                   titel="Data Engineer (w/m/d)"),
        ]
    )

    assert ergebnisse == ["weitergereicht", "doppelt"]
    assert producer.gesendet == ["10001-1-S"]


def test_verschiedene_stellen_kommen_beide_durch():
    ergebnisse, _, producer = lauf(
        [stelle("10001-1-S"), stelle("10001-2-S", firma="Andere GmbH")]
    )

    assert ergebnisse == ["weitergereicht", "weitergereicht"]
    assert len(producer.gesendet) == 2


def test_ausschlussbegriff_sortiert_aus():
    ergebnisse, _, producer = lauf(
        [stelle("10001-1-S", titel="Senior Data Engineer")], ausschluss=("senior",)
    )

    assert ergebnisse == ["aussortiert"]
    assert producer.gesendet == []


def test_archiviert_wird_vor_jeder_pruefung():
    """Das Archiv soll den vollstaendigen Rohbestand halten."""
    _, archiv, _ = lauf(
        [stelle("10001-1-S", titel="Senior Data Engineer")], ausschluss=("senior",)
    )

    assert archiv.abgelegt == ["10001-1-S"]


def test_anzeige_ohne_firma_laeuft_ueber_die_kennung_weiter():
    """Ohne Fingerabdruck bleibt der Abgleich ueber die Referenznummer."""
    ohne_firma = {"referenznummer": "10001-9-S", "stellenangebotsTitel": "Data Engineer"}

    ergebnisse, _, producer = lauf([ohne_firma, dict(ohne_firma)])

    assert ergebnisse == ["weitergereicht", "bekannt"]
    assert producer.gesendet == ["10001-9-S"]
