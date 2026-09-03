"""Test der Deduplizierung gegen DynamoDB."""
import pytest
from botocore.exceptions import ClientError

from filter_dedup.dedup import Dedup


class FakeTabelle:
    """Merkt sich Schluessel und ahmt den bedingten Schreibvorgang nach."""

    def __init__(self):
        self.bekannt = set()
        self.eintraege = []

    def put_item(self, Item, ConditionExpression=None):
        schluessel = Item["referenznummer"]
        if schluessel in self.bekannt:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "x"}},
                "PutItem",
            )
        self.bekannt.add(schluessel)
        self.eintraege.append(Item)


@pytest.fixture
def dedup(monkeypatch):
    tabelle = FakeTabelle()
    objekt = Dedup.__new__(Dedup)
    objekt._tabelle = tabelle
    objekt._aufbewahrung_sekunden = 180 * 24 * 3600
    return objekt, tabelle


def test_erste_anzeige_ist_neu(dedup):
    objekt, _ = dedup
    assert objekt.ist_neu("ref-1", "Data Engineer") is True


def test_zweite_anzeige_mit_gleichem_schluessel_ist_bekannt(dedup):
    objekt, _ = dedup
    objekt.ist_neu("ref-1", "Data Engineer")

    assert objekt.ist_neu("ref-1", "Data Engineer") is False


def test_eintrag_bekommt_ablaufzeitpunkt_und_status(dedup):
    objekt, tabelle = dedup
    objekt.ist_neu("ref-1", "Data Engineer")

    eintrag = tabelle.eintraege[0]
    assert eintrag["status"] == "GEFUNDEN"
    assert eintrag["ablauf_zeitpunkt"] > eintrag["erfasst_am"]


def test_andere_fehler_werden_nicht_verschluckt(dedup):
    objekt, tabelle = dedup

    def kaputt(**_):
        raise ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "x"}},
            "PutItem",
        )

    tabelle.put_item = kaputt

    with pytest.raises(ClientError):
        objekt.ist_neu("ref-1")


# --- Quellenuebergreifender Abgleich ----------------------------------


def test_erster_merkposten_ist_neu(dedup):
    objekt, _ = dedup

    assert objekt.ist_inhaltlich_neu("fp#abc", "10001-1-S") is True


def test_zweite_quelle_mit_gleichem_inhalt_faellt_durch(dedup):
    """Andere Referenznummer, gleicher Fingerabdruck - schon gemeldet."""
    objekt, _ = dedup
    objekt.ist_inhaltlich_neu("fp#abc", "10001-1-S")

    assert objekt.ist_inhaltlich_neu("fp#abc", "arbeitnow:data-engineer") is False


def test_merkposten_notiert_die_zuerst_gesehene_anzeige(dedup):
    objekt, tabelle = dedup
    objekt.ist_inhaltlich_neu("fp#abc", "10001-1-S")

    eintrag = tabelle.eintraege[-1]
    assert eintrag["referenznummer"] == "fp#abc"
    assert eintrag["zuerst_gesehen_als"] == "10001-1-S"
    assert eintrag["ablauf_zeitpunkt"] > eintrag["erfasst_am"]


def test_merkposten_bekommt_keinen_status(dedup):
    """Er ist keine Anzeige und hat im Bewerbungsverlauf nichts zu suchen."""
    objekt, tabelle = dedup
    objekt.ist_inhaltlich_neu("fp#abc", "10001-1-S")

    assert "status" not in tabelle.eintraege[-1]


def test_kennung_und_inhalt_stehen_sich_nicht_im_weg(dedup):
    """Beide Schluessel liegen in derselben Tabelle, aber getrennt."""
    objekt, _ = dedup
    objekt.ist_neu("10001-1-S", "Data Engineer")

    assert objekt.ist_inhaltlich_neu("fp#abc", "10001-1-S") is True
