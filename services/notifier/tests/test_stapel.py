"""Test der Stapellogik."""
from notifier.config import MailConfig
from notifier.main import stapel_faellig

CONFIG = MailConfig(
    absender="a@example.com",
    empfaenger="b@example.com",
    max_stapel=25,
    wartezeit_sekunden=60,
)


def test_leerer_stapel_geht_nie_raus():
    assert stapel_faellig(0, letzte_nachricht=0, mail_config=CONFIG, jetzt=10_000) is False


def test_voller_stapel_geht_sofort_raus():
    assert stapel_faellig(25, letzte_nachricht=100, mail_config=CONFIG, jetzt=101) is True


def test_teilstapel_wartet_noch():
    assert stapel_faellig(3, letzte_nachricht=100, mail_config=CONFIG, jetzt=130) is False


def test_teilstapel_geht_nach_der_wartezeit_raus():
    assert stapel_faellig(3, letzte_nachricht=100, mail_config=CONFIG, jetzt=161) is True


def test_wartefunktion_bricht_bei_stoppsignal_ab(monkeypatch):
    """Ein Stoppsignal muss die Wartezeit sofort beenden."""
    import notifier.main as m

    monkeypatch.setattr(m, "_laeuft", False)
    beginn = __import__("time").monotonic()
    m._warte(30)

    assert __import__("time").monotonic() - beginn < 1
