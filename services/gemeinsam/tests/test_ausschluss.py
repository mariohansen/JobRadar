"""Tests der Ausschlussliste, die filter-dedup und tracker teilen."""
from gemeinsam import ausschluss


def test_standardliste_deckt_die_bekannten_gruppen_ab():
    for begriff in ("senior", "sr", "lead", "teamlead", "head of", "praktikum", "werkstudent"):
        assert begriff in ausschluss.STANDARD


def test_grund_nennt_den_ersten_treffer():
    assert ausschluss.grund("Senior Data Engineer (m/w/d)") == "senior"
    assert ausschluss.grund("(Sr.) Quality Assurance Engineer") == "sr"
    assert ausschluss.grund("Teamlead Softwareentwicklung") == "teamlead"


def test_grund_ist_none_bei_sauberer_stelle():
    assert ausschluss.grund("Data Engineer (m/w/d)") is None
    assert ausschluss.grund("Junior Data Engineer") is None


def test_grund_prueft_den_wortanfang():
    """Israel enthaelt 'sr', Verkaufsleiter endet auf 'leiter'."""
    assert ausschluss.grund("Softwareentwickler Israel Desk") is None
    assert ausschluss.grund("Verkaufsleiter Region Nord", ("leiter",)) is None


def test_grund_nimmt_eine_eigene_liste():
    assert ausschluss.grund("Senior Data Engineer", ("lead",)) is None
    assert ausschluss.grund("Lead Data Engineer", ("lead",)) == "lead"


def test_grund_vertraegt_leeren_text():
    assert ausschluss.grund("") is None
    assert ausschluss.grund(None) is None


def test_aus_umgebung_faellt_auf_die_vorgabe_zurueck():
    assert ausschluss.aus_umgebung(None) == ausschluss.STANDARD
    assert ausschluss.aus_umgebung("   ") == ausschluss.STANDARD


def test_aus_umgebung_liest_die_eigene_liste():
    assert ausschluss.aus_umgebung("Lead, Head of ,principal") == ("lead", "head of", "principal")
