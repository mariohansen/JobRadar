"""Tests der Spaltenzuordnung.

Die Anzeigen sind auf die Felder gekuerzt, um die es jeweils geht - eine
vollstaendige API-Antwort wuerde den Punkt eher verdecken als zeigen.
"""
from gemeinsam import passung
from gemeinsam import profil as pr

from tracker import felder
from tracker.store import Eintrag

EINTRAG = Eintrag(
    referenznummer="10001-1003552327-S",
    titel="Data Engineer (m/w/d)",
    status="BEWORBEN",
    erfasst_am=1756684800,  # 2025-09-01
    geaendert_am=None,
)

PROFIL = pr.Profil(
    faehigkeiten={"Java": 5, "Spring": 6, "SQL": 2, "Docker": 1},
    quellen=("Lebenslauf.pdf",),
)

ROH = {
    "stellenangebotsTitel": "Data Engineer (m/w/d)",
    "firma": "Beispiel & Partner GmbH",
    "stellenlokationen": [{"adresse": {"plz": "20095", "ort": "Hamburg"}}],
    "datumErsteVeroeffentlichung": "2025-08-28",
    "homeofficeprozent": 100,
}


def test_alle_spalten_sind_genau_einer_stufe_zugeordnet():
    """Jede Spalte ausser Nr. wird automatisch, vorbelegt oder gar nicht gefuellt."""
    ueberschneidung = felder.AUTOMATISCH & felder.VORSCHLAG
    assert not ueberschneidung

    unbekannt = (felder.AUTOMATISCH | felder.VORSCHLAG) - set(felder.SPALTEN_MIT_PASSUNG)
    assert not unbekannt


def test_nichts_bleibt_mehr_von_hand():
    """Termine und Notizen sind raus - gepflegt wird nur der Status."""
    von_hand = [
        s for s in felder.SPALTEN
        if s not in felder.AUTOMATISCH and s not in felder.VORSCHLAG
    ]
    assert von_hand == []


def test_passung_steht_vorn_wenn_sie_dazukommt():
    """Die Tabelle wird nach ihr sortiert - dann gehoert sie in Sichtweite."""
    assert felder.SPALTEN_MIT_PASSUNG.index("Passung") < felder.SPALTEN_MIT_PASSUNG.index("Firma")
    ohne_passung = tuple(s for s in felder.SPALTEN_MIT_PASSUNG if s not in felder.PASSUNGSSPALTEN)
    assert ohne_passung == felder.SPALTEN_STANDARD


def test_zeile_enthaelt_die_kerndaten():
    zeile = felder.zeile(EINTRAG, ROH)

    assert zeile["Firma"] == "Beispiel & Partner GmbH"
    assert zeile["Position"] == "Data Engineer (m/w/d)"
    assert zeile["Standort"] == "20095 Hamburg"
    assert zeile["Homeoffice-Modell"] == "100 % remote"
    assert zeile["Status"] == "Abgeschickt"
    assert zeile["Link zur Ausschreibung"].endswith("10001-1003552327-S")
    assert zeile[felder.SPALTE_REFERENZ] == "10001-1003552327-S"


def test_zeile_kommt_ohne_archiv_und_detail_aus():
    """Faellt das Archiv aus, bleibt der Titel aus der Tabelle stehen."""
    zeile = felder.zeile(EINTRAG)

    assert zeile["Position"] == "Data Engineer (m/w/d)"
    assert zeile["Firma"] == ""
    assert zeile["Homeoffice-Modell"] == ""
    assert zeile["Gehalt"] == ""


def test_homeoffice_unterscheidet_die_stufen():
    assert felder.homeoffice({"homeofficeprozent": 100}) == "100 % remote"
    assert felder.homeoffice({"homeofficeprozent": 40}) == "hybrid, 40 % Homeoffice"
    assert felder.homeoffice({"homeofficetyp": "NACH_VEREINBARUNG"}) == "nach Vereinbarung"
    assert felder.homeoffice({"homeofficemoeglich": True}) == "möglich, Umfang offen"


def test_ohne_angabe_bleibt_homeoffice_leer():
    """Frueher stand hier "vor Ort" - eine Behauptung ohne Grundlage."""
    assert felder.homeoffice({"stellenangebotsTitel": "x"}) == ""


def test_homeoffice_kommt_aus_dem_anzeigentext():
    """Die Schnittstellenfelder sind meist leer, der Text sagt etwas."""
    roh = {"stellenangebotsTitel": "x"}

    assert felder.homeoffice(roh, {}, "100 % Homeoffice innerhalb Deutschlands") == "100 % remote"
    assert felder.homeoffice(roh, {}, "ein hybrides Arbeitsmodell") == "hybrid, Umfang offen"
    assert felder.homeoffice(roh, {}, "Mobiles Arbeiten nach Absprache") == "möglich, Umfang offen"
    assert felder.homeoffice(roh, {}, "2 Tage Homeoffice pro Woche") == "hybrid, 2 Tage/Woche"


def test_prozentzahl_schlaegt_den_text():
    """Eine Zahl der Schnittstelle ist belastbarer als eine Formulierung."""
    roh = {"homeofficeprozent": 40}

    assert felder.homeoffice(roh, {}, "100 % Homeoffice") == "hybrid, 40 % Homeoffice"


def test_homeoffice_faellt_auf_die_detailansicht_zurueck():
    """Die Trefferliste nennt den Typ meist nicht, die Detailansicht schon."""
    assert felder.homeoffice({}, {"homeofficetyp": "NACH_VEREINBARUNG"}) == "nach Vereinbarung"
    assert felder.homeoffice({"stellenangebotsTitel": "x"}, {"homeofficemoeglich": True}) == (
        "möglich, Umfang offen"
    )


def test_nach_vereinbarung_gilt_nicht_als_remote():
    """Wie im Poller: der Wert sagt nur, dass darueber zu reden ist."""
    text = felder.homeoffice({"homeofficetyp": "NACH_VEREINBARUNG", "homeofficemoeglich": True})

    assert "remote" not in text
    assert text == "nach Vereinbarung"


def test_standort_fasst_mehrere_orte_zusammen_ohne_doppelte():
    roh = {
        "stellenlokationen": [
            {"adresse": {"plz": "20095", "ort": "Hamburg"}},
            {"adresse": {"plz": "20095", "ort": "Hamburg"}},
            {"adresse": {"ort": "Lüneburg"}},
        ]
    }

    assert felder.standort(roh, {}) == "20095 Hamburg / Lüneburg"


def test_standort_faellt_auf_die_detailansicht_zurueck():
    detail = {"arbeitsorte": [{"plz": "22179", "ort": "Hamburg"}]}

    assert felder.standort({}, detail) == "22179 Hamburg"


def test_ansprechpartner_aus_den_kontaktfeldern():
    detail = {"kontakt": {"anrede": "Frau", "vorname": "Anke", "nachname": "Meyer"}}

    assert felder.ansprechpartner(detail) == "Frau Anke Meyer"


def test_ansprechpartner_aus_dem_anzeigentext():
    detail = {"stellenangebotsBeschreibung": "Ihre Ansprechpartnerin ist Frau Dr. Anke Meyer."}

    assert "Anke Meyer" in felder.ansprechpartner(detail)


def test_ansprechpartner_liest_auch_den_alten_feldnamen():
    """Die Schnittstelle hat das Feld umbenannt - der Altname bleibt Rueckfall."""
    detail = {"stellenbeschreibung": "Ihre Ansprechpartnerin ist Frau Anke Meyer."}

    assert "Anke Meyer" in felder.ansprechpartner(detail)


def test_kontakt_liest_mail_und_telefon_aus_dem_text():
    detail = {
        "stellenangebotsBeschreibung": (
            "Bewerbungen an bewerbung@beispiel.de oder telefonisch "
            "unter 040 123456-78."
        )
    }

    kontakt = felder.kontakt(detail)

    assert "bewerbung@beispiel.de" in kontakt
    assert "040 123456-78" in kontakt


def test_kontakt_gesamt_fasst_name_und_erreichbarkeit_zusammen():
    detail = {
        "stellenangebotsBeschreibung": (
            "Ihre Ansprechpartnerin ist Frau Anke Meyer. "
            "Bewerbungen an bewerbung@beispiel.de."
        )
    }

    gesamt = felder.kontakt_gesamt(detail)

    assert "Anke Meyer" in gesamt
    assert "bewerbung@beispiel.de" in gesamt


def test_name_endet_am_satzende():
    """Sonst wandert das erste Wort des naechsten Satzes in den Namen."""
    detail = {
        "stellenangebotsBeschreibung": "Ihre Ansprechpartnerin ist Frau Dr. Sabine Kern. Wir freuen uns."
    }

    assert felder.ansprechpartner(detail) == "Frau Dr. Sabine Kern"


def test_mailadresse_endet_am_satzende():
    detail = {"stellenangebotsBeschreibung": "Bewerbungen bitte an jobs@cloudhaus.de."}

    assert felder.kontakt(detail) == "jobs@cloudhaus.de"


def test_telefonmuster_schlaegt_nicht_bei_jahreszahlen_an():
    detail = {"stellenangebotsBeschreibung": "Gegruendet 1998, seit 2015 in Hamburg."}

    assert felder.kontakt(detail) == ""


def test_bewerbungsweg_nennt_nur_den_abweichenden_kanal():
    assert felder.bewerbungsweg({"externeURL": "https://x.de/job"}, {}) == "Online-Portal des Arbeitgebers"
    assert felder.bewerbungsweg({}, {"kontakt": {"email": "a@b.de"}}) == "E-Mail"
    # Der Regelfall - Bewerbung ueber die Jobboerse - bleibt leer.
    assert felder.bewerbungsweg({}, {"stellenangebotsBeschreibung": "Text"}) == ""


def test_gehalt_bevorzugt_die_angabe_der_anzeige():
    detail = {"verguetung": "55.000 bis 65.000 EUR im Jahr"}

    assert felder.gehalt({}, detail) == "55.000 bis 65.000 EUR im Jahr"


def test_gehalt_faellt_auf_den_tarifvertrag_sonst_leer():
    assert felder.gehalt({}, {"tarifvertrag": "TVöD E12"}) == "nach Tarifvertrag (TVöD E12)"
    assert felder.gehalt({}, {}) == ""


# --- Zusammenspiel mit der Passungsbewertung --------------------------
def test_passungsspalten_entstehen_nur_mit_bewertung():
    eintrag = Eintrag("10001-1-S", "Java Entwickler", "GEFUNDEN", 1756684800, None)

    ohne = felder.zeile(eintrag)
    mit = felder.zeile(eintrag, bewertung=passung.bewerte(PROFIL, "Java", "Spring, SQL"))

    assert "Passung" not in ohne
    assert mit["Passung"] in (passung.STUFE_A, passung.STUFE_B, passung.STUFE_C)
    assert mit["Punkte"] == mit["Punkte"]  # Zahl, nicht Text
    assert isinstance(mit["Punkte"], int)


def test_punkte_bleiben_leer_wenn_nicht_bewertbar():
    eintrag = Eintrag("10001-1-S", "Entwickler", "GEFUNDEN", 1756684800, None)

    zeile = felder.zeile(eintrag, bewertung=passung.bewerte(PROFIL, "Entwickler", ""))

    assert zeile["Passung"] == passung.STUFE_D
    assert zeile["Punkte"] == ""


def test_alter_und_entfernung_stehen_als_zahl_in_der_zeile():
    roh = {**ROH, "entfernung": 12.4}

    zeile = felder.zeile(EINTRAG, roh)

    assert isinstance(zeile["Alter (Tage)"], int)
    assert zeile["Entfernung (km)"] == 12.4


def test_fehlende_angaben_bleiben_leere_zellen():
    """Eine Null waere eine Behauptung, die die Daten nicht hergeben."""
    zeile = felder.zeile(EINTRAG, {"stellenangebotsTitel": "Entwickler"})

    assert zeile["Alter (Tage)"] == ""
    assert zeile["Entfernung (km)"] == ""


# --- Mehrere Quellen ---------------------------------------------------


def test_quelle_steht_in_der_zeile():
    zeile = felder.zeile(EINTRAG, {**ROH, "quelle": "arbeitnow"})

    assert zeile["Quelle"] == "arbeitnow"


def test_alte_eintraege_ohne_quelle_gelten_als_bundesagentur():
    """Das Archiv reicht weiter zurueck als das Feld."""
    assert felder.zeile(EINTRAG, ROH)["Quelle"] == "arbeitsagentur"


def test_link_der_bundesagentur_kommt_aus_der_referenznummer():
    zeile = felder.zeile(EINTRAG, ROH)

    assert zeile["Link zur Ausschreibung"].startswith(felder.STELLENLINK)
    assert zeile["Link zur Ausschreibung"].endswith(EINTRAG.referenznummer)


def test_fremde_quelle_verlinkt_ihre_eigene_adresse():
    """Die Referenznummer von Arbeitnow fuehrt bei der Agentur ins Leere."""
    roh = {**ROH, "quelle": "arbeitnow", "externeURL": "https://arbeitnow.example/a"}

    zeile = felder.zeile(EINTRAG, roh)

    assert zeile["Link zur Ausschreibung"] == "https://arbeitnow.example/a"


def test_fremde_quelle_ohne_adresse_faellt_auf_die_agentur_zurueck():
    zeile = felder.zeile(EINTRAG, {**ROH, "quelle": "arbeitnow"})

    assert zeile["Link zur Ausschreibung"].startswith(felder.STELLENLINK)


def test_anzeigentext_wird_auch_in_der_anzeige_selbst_gefunden():
    """Fremde Quellen liefern ihn mit, statt in einer Detailansicht."""
    roh = {
        **ROH,
        "quelle": "arbeitnow",
        "stellenangebotsBeschreibung": (
            "Wir bieten ein Jobticket und 30 Tage Urlaub. "
            "Bewerbungen an jobs@beispiel.de."
        ),
    }

    zeile = felder.zeile(EINTRAG, roh)

    assert "Jobticket / ÖPNV" in zeile["Benefits"]
    assert "30+ Tage Urlaub" in zeile["Benefits"]
    assert "jobs@beispiel.de" in zeile["Kontakt"]


# --- Status und Gehalt aus dem Text ------------------------------------


def test_status_gefunden_bleibt_in_der_tabelle_leer():
    """Dreihundertmal 'Gefunden' traegt nichts bei."""
    eintrag = Eintrag("10001-1-S", "Data Engineer", "GEFUNDEN", 1756684800, None)

    assert felder.zeile(eintrag)["Status"] == ""


def test_gehalt_kommt_aus_dem_anzeigentext():
    detail = {"stellenangebotsBeschreibung": "Wir zahlen 70.000 EUR im Jahr."}

    assert felder.zeile(EINTRAG, ROH, detail)["Gehalt"] == "70.000 EUR"


def test_gehaltsspanne_wird_ganz_uebernommen():
    assert felder.gehalt_aus_text("Gehalt: 55.000 - 65.000 EUR") == "55.000 - 65.000 EUR"


def test_tarifgruppe_zaehlt_als_gehaltsangabe():
    assert felder.gehalt_aus_text("Verguetung nach TVöD E 13") == "TVöD E 13"
    assert felder.gehalt_aus_text("Entgeltgruppe 13") == "Entgeltgruppe 13"


def test_jahreszahlen_sind_keine_gehaelter():
    assert felder.gehalt_aus_text("Gegruendet 1998, 250 Mitarbeiter") == ""
    assert felder.gehalt_aus_text("") == ""


def test_entfernung_kommt_notfalls_aus_dem_ortsnamen(monkeypatch):
    """Nur die Bundesagentur liefert sie mit; die uebrigen Quellen nicht."""
    monkeypatch.setenv("JOBSUCHE_WO", "Hamburg")
    roh = {"stellenlokationen": [{"adresse": {"ort": "Lüneburg"}}]}

    assert 40 < felder.entfernung_km(roh) < 50


def test_gemeldete_entfernung_hat_vorrang(monkeypatch):
    monkeypatch.setenv("JOBSUCHE_WO", "Hamburg")
    roh = {"entfernung": 4, "stellenlokationen": [{"adresse": {"ort": "Lüneburg"}}]}

    assert felder.entfernung_km(roh) == 4.0


def test_remote_region_bekommt_keine_entfernung(monkeypatch):
    monkeypatch.setenv("JOBSUCHE_WO", "Hamburg")

    assert felder.entfernung_km({"stellenlokationen": [{"adresse": {"ort": "EMEA"}}]}) is None
    assert felder.entfernung_km({}) is None
