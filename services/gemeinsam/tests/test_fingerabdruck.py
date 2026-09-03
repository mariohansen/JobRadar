"""Tests des quellenuebergreifenden Fingerabdrucks."""
from gemeinsam import fingerabdruck as fa


def job(firma="Beispiel GmbH", titel="Data Engineer (m/w/d)", ort="Hamburg", plz=""):
    return {
        "firma": firma,
        "stellenangebotsTitel": titel,
        "stellenlokationen": [{"adresse": {"plz": plz, "ort": ort}}],
    }


# --- Normalisierung ---------------------------------------------------


def test_geschlechtszusatz_faellt_weg():
    assert fa.titel("Data Engineer (m/w/d)") == fa.titel("Data Engineer (w/m/d)")
    assert fa.titel("Data Engineer (all genders)") == fa.titel("Data Engineer")
    assert fa.titel("Data Engineer (gn)") == "data engineer"


def test_rechtsform_faellt_weg():
    assert fa.firma("Beispiel GmbH & Co. KG") == fa.firma("Beispiel GmbH")
    assert fa.firma("Beispiel AG") == "beispiel"
    assert fa.firma("Beispiel Deutschland GmbH") == "beispiel"


def test_ort_verliert_plz_und_land():
    assert fa.ort("20095 Hamburg") == "hamburg"
    assert fa.ort("Hamburg, Deutschland") == "hamburg"
    assert fa.ort("Hamburg") == "hamburg"


# --- Fingerabdruck ----------------------------------------------------


def test_dieselbe_stelle_auf_zwei_portalen_faellt_zusammen():
    bei_der_agentur = job(firma="Beispiel GmbH & Co. KG", plz="20095")
    auf_arbeitnow = job(firma="Beispiel GmbH", titel="Data Engineer (w/m/d)",
                        ort="Hamburg, Deutschland")

    assert fa.berechne(bei_der_agentur) == fa.berechne(auf_arbeitnow)


def test_erfahrungsstufe_bleibt_unterscheidbar():
    """Senior und nicht-Senior sind verschiedene Stellen."""
    assert fa.berechne(job()) != fa.berechne(job(titel="Senior Data Engineer (m/w/d)"))


def test_verschiedene_arbeitgeber_bleiben_getrennt():
    assert fa.berechne(job()) != fa.berechne(job(firma="Andere GmbH"))


def test_verschiedene_orte_bleiben_getrennt():
    assert fa.berechne(job()) != fa.berechne(job(ort="Berlin"))


def test_ohne_arbeitgeber_oder_titel_kein_abdruck():
    """Zu grob waere schlimmer als gar nicht - dann lieber doppelt melden."""
    assert fa.berechne(job(firma="")) is None
    assert fa.berechne(job(titel="")) is None
    assert fa.berechne({}) is None


def test_fehlender_ort_ist_kein_hindernis():
    ohne_ort = {"firma": "Beispiel GmbH", "stellenangebotsTitel": "Data Engineer"}

    assert fa.berechne(ohne_ort) is not None


# --- Schluessel -------------------------------------------------------


def test_schluessel_traegt_das_praefix():
    schluessel = fa.schluessel(job())

    assert schluessel.startswith(fa.PRAEFIX)
    assert fa.ist_merkposten(schluessel)


def test_schluessel_ohne_abdruck_ist_none():
    assert fa.schluessel({}) is None


def test_echte_referenznummer_ist_kein_merkposten():
    assert fa.ist_merkposten("10001-1003552327-S") is False
    assert fa.ist_merkposten("arbeitnow:data-engineer-hamburg-1") is False
    assert fa.ist_merkposten(None) is False
