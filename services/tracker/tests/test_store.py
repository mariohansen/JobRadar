"""Tests des Datenzugriffs.

Die DynamoDB-Tabelle wird durch ein Doppel ersetzt, das die hier
genutzten Eigenschaften nachbildet: bedingtes Aktualisieren und
seitenweises Scannen.
"""
import pytest
from botocore.exceptions import ClientError

from tracker import status as st
from tracker.store import Eintrag, Store, UnbekannteAnzeige


class FakeTabelle:
    def __init__(self, items=None):
        self.items = {i["referenznummer"]: dict(i) for i in (items or [])}
        self.letzter_ausdruck = ""

    def get_item(self, Key):
        eintrag = self.items.get(Key["referenznummer"])
        return {"Item": dict(eintrag)} if eintrag else {}

    def scan(self, **kwargs):
        werte = [dict(i) for i in self.items.values()]
        if "FilterExpression" in kwargs:
            gesucht = kwargs["ExpressionAttributeValues"][":s"]
            werte = [i for i in werte if i.get("status") == gesucht]
        return {"Items": werte}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeValues, **kwargs):
        self.letzter_ausdruck = UpdateExpression
        schluessel = Key["referenznummer"]
        if schluessel not in self.items:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "x"}},
                "UpdateItem",
            )
        eintrag = self.items[schluessel]
        eintrag["status"] = ExpressionAttributeValues[":s"]
        eintrag["geaendert_am"] = ExpressionAttributeValues[":jetzt"]
        if "REMOVE ablauf_zeitpunkt" in UpdateExpression:
            eintrag.pop("ablauf_zeitpunkt", None)
        return {"Attributes": dict(eintrag)}


def baue_store(items=None):
    store = Store.__new__(Store)
    tabelle = FakeTabelle(items)
    store._tabelle = tabelle
    return store, tabelle


ANZEIGE = {
    "referenznummer": "ref-1",
    "titel": "Data Engineer",
    "status": st.GEFUNDEN,
    "erfasst_am": 1700000000,
    "ablauf_zeitpunkt": 1800000000,
}


def test_eintrag_wird_gelesen():
    store, _ = baue_store([ANZEIGE])

    eintrag = store.hole("ref-1")

    assert eintrag.titel == "Data Engineer"
    assert eintrag.status == st.GEFUNDEN


def test_unbekannte_referenz_beim_lesen():
    store, _ = baue_store([ANZEIGE])

    with pytest.raises(UnbekannteAnzeige):
        store.hole("gibt-es-nicht")


def test_liste_filtert_nach_status():
    zweite = {**ANZEIGE, "referenznummer": "ref-2", "status": st.BEWORBEN}
    store, _ = baue_store([ANZEIGE, zweite])

    treffer = list(store.liste(st.BEWORBEN))

    assert [e.referenznummer for e in treffer] == ["ref-2"]


def test_liste_ohne_filter_gibt_alles():
    zweite = {**ANZEIGE, "referenznummer": "ref-2", "status": st.BEWORBEN}
    store, _ = baue_store([ANZEIGE, zweite])

    assert len(list(store.liste())) == 2


def test_status_wird_gesetzt():
    store, _ = baue_store([ANZEIGE])

    eintrag = store.setze_status("ref-1", "beworben")

    assert eintrag.status == st.BEWORBEN
    assert eintrag.geaendert_am is not None


def test_bewerbung_hebt_die_aufbewahrungsfrist_auf():
    """Sobald eine Bewerbung laeuft, darf die TTL den Eintrag nicht loeschen."""
    store, tabelle = baue_store([ANZEIGE])

    store.setze_status("ref-1", st.BEWORBEN)

    assert "ablauf_zeitpunkt" not in tabelle.items["ref-1"]
    assert "REMOVE ablauf_zeitpunkt" in tabelle.letzter_ausdruck


def test_gefunden_behaelt_die_aufbewahrungsfrist():
    store, tabelle = baue_store([ANZEIGE])

    store.setze_status("ref-1", st.GEFUNDEN)

    assert "ablauf_zeitpunkt" in tabelle.items["ref-1"]


def test_unbekannter_status_wird_abgewiesen():
    store, _ = baue_store([ANZEIGE])

    with pytest.raises(st.UnbekannterStatus):
        store.setze_status("ref-1", "IRGENDWAS")


def test_status_setzen_auf_unbekannte_anzeige():
    store, _ = baue_store([ANZEIGE])

    with pytest.raises(UnbekannteAnzeige):
        store.setze_status("gibt-es-nicht", st.BEWORBEN)


def test_eintrag_vertraegt_fehlende_felder():
    eintrag = Eintrag.aus_item({"referenznummer": "ref-x"})

    assert eintrag.titel == ""
    assert eintrag.status == st.GEFUNDEN
    assert eintrag.geaendert_am is None
