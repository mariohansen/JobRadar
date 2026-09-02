"""Tests der Statuslogik."""
import pytest

from tracker import status as st


def test_kleinschreibung_wird_normalisiert():
    assert st.pruefe("beworben") == "BEWORBEN"


def test_umgebende_leerzeichen_stoeren_nicht():
    assert st.pruefe("  interview  ") == "INTERVIEW"


def test_unbekannter_status_wird_abgewiesen():
    with pytest.raises(st.UnbekannterStatus, match="Erlaubt sind"):
        st.pruefe("VIELLEICHT")


def test_gefundene_anzeige_gilt_nicht_als_verfolgt():
    assert st.ist_verfolgt(st.GEFUNDEN) is False


def test_jede_weitere_stufe_gilt_als_verfolgt():
    for zustand in (st.BEWORBEN, st.INTERVIEW, st.ZUSAGE, st.ABSAGE):
        assert st.ist_verfolgt(zustand) is True


def test_reihenfolge_bildet_den_bewerbungsverlauf_ab():
    assert st.ALLE.index(st.GEFUNDEN) < st.ALLE.index(st.BEWORBEN)
    assert st.ALLE.index(st.BEWORBEN) < st.ALLE.index(st.INTERVIEW)
