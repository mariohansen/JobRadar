"""Tests der Filterlogik."""
from filter_dedup.matching import durchsuchbarer_text, passt

AUSSCHLUSS = ("praktikum", "werkstudent")


def job(titel, hauptberuf="", alle=None):
    return {
        "stellenangebotsTitel": titel,
        "hauptberuf": hauptberuf,
        "alleBerufe": alle or [],
    }


def test_regulaere_stelle_kommt_durch():
    assert passt(job("Data Engineer (m/w/d)"), AUSSCHLUSS, ()) is True


def test_praktikum_faellt_heraus():
    assert passt(job("Praktikum Data Engineering"), AUSSCHLUSS, ()) is False


def test_ausschluss_greift_auch_in_grossschreibung():
    assert passt(job("WERKSTUDENT Softwareentwicklung"), AUSSCHLUSS, ()) is False


def test_ausschluss_greift_auch_in_nebenberufen():
    anzeige = job("Entwickler", alle=["Werkstudent Informatik"])
    assert passt(anzeige, AUSSCHLUSS, ()) is False


def test_pflichtbegriff_fehlt():
    assert passt(job("Frontend Entwickler"), AUSSCHLUSS, ("python", "data")) is False


def test_pflichtbegriff_vorhanden():
    assert passt(job("Python Entwickler"), AUSSCHLUSS, ("python", "data")) is True


def test_leere_pflichtliste_laesst_alles_durch():
    assert passt(job("Irgendwas"), (), ()) is True


def test_durchsuchbarer_text_vertraegt_fehlende_felder():
    """Eine Anzeige ohne Titel und Berufe darf keinen Fehler ausloesen."""
    assert durchsuchbarer_text({}).strip() == ""
    assert passt({}, AUSSCHLUSS, ()) is True


SENIOR_AUSSCHLUSS = ("senior", "sr.")


def test_senior_stelle_faellt_heraus():
    assert passt(job("Senior Data Engineer (m/w/d)"), SENIOR_AUSSCHLUSS, ()) is False


def test_abgekuerztes_senior_faellt_heraus():
    """Die Bundesagentur fuehrt solche Stellen auch als (Sr.)."""
    assert passt(job("(Sr.) Quality Assurance Engineer"), SENIOR_AUSSCHLUSS, ()) is False


def test_senior_in_klammern_faellt_heraus():
    assert passt(job("(Senior) Data Engineer (gn)"), SENIOR_AUSSCHLUSS, ()) is False


def test_stelle_ohne_senior_bleibt():
    assert passt(job("Data Engineer (m/w/d)"), SENIOR_AUSSCHLUSS, ()) is True


def test_junior_bleibt_erhalten():
    assert passt(job("Junior Data Engineer"), SENIOR_AUSSCHLUSS, ()) is True


def test_sr_ohne_punkt_faellt_heraus():
    assert passt(job("Sr Data Engineer"), ("senior", "sr"), ()) is False


def test_sr_mit_punkt_faellt_ebenfalls_heraus():
    assert passt(job("(Sr.) Quality Assurance Engineer"), ("senior", "sr"), ()) is False


def test_sr_schlaegt_nicht_mitten_im_wort_an():
    """Teilzeichenketten wuerden hier falsch greifen: Israel enthaelt sr."""
    assert passt(job("Softwareentwickler Israel Desk (m/w/d)"), ("senior", "sr"), ()) is True


def test_praktikum_erfasst_weiterhin_zusammensetzungen():
    assert passt(job("Praktikumsstelle Data Engineering"), ("praktikum",), ()) is False


def test_begriff_am_wortende_schlaegt_nicht_an():
    assert passt(job("Verkaufsleiter"), ("leiter",), ()) is True


FUEHRUNG = ("lead", "teamlead", "leiter", "teamleiter", "principal", "staff", "head of")


def test_lead_faellt_heraus():
    assert passt(job("Lead Developer Mobile Apps"), FUEHRUNG, ()) is False


def test_leader_wird_von_lead_miterfasst():
    assert passt(job("Team Leader Data Platform"), FUEHRUNG, ()) is False


def test_teamlead_ohne_leerzeichen_faellt_heraus():
    """Hier steht lead nicht am Wortanfang, deshalb der eigene Eintrag."""
    assert passt(job("Teamlead Softwareentwicklung"), FUEHRUNG, ()) is False


def test_teamleiter_faellt_heraus():
    assert passt(job("Teamleiter tomedo Swift / Objective-C"), FUEHRUNG, ()) is False


def test_leiter_faellt_heraus():
    assert passt(job("Leiter (m/w/d) Softwareentwicklung"), FUEHRUNG, ()) is False


def test_principal_und_staff_fallen_heraus():
    assert passt(job("Principal DevSecOps Engineer"), FUEHRUNG, ()) is False
    assert passt(job("Staff Data Engineer (m/w/d)"), FUEHRUNG, ()) is False


def test_head_of_faellt_heraus():
    assert passt(job("Head of Data Engineering"), FUEHRUNG, ()) is False


def test_junior_manager_bleibt_erhalten():
    """manager steht bewusst nicht auf der Liste - der Begriff kommt auch
    in Einstiegsstellen vor."""
    assert passt(job("Junior Customer Success Manager:in"), FUEHRUNG, ()) is True


def test_normale_entwicklerstelle_bleibt():
    assert passt(job("Data Engineer (m/w/d)"), FUEHRUNG, ()) is True
