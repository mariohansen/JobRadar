"""Verzeichnis fachlicher Begriffe.

Dieselbe Bauart wie benefits.py und aus demselben Grund: ein festes
Verzeichnis ist nachvollziehbar, laeuft ohne Netz und kostet nichts. Was
nicht darin steht, wird nicht gefunden - deshalb laesst sich das Profil
von Hand ergaenzen.

Dieses Verzeichnis enthaelt nichts Persoenliches. Es beschreibt, welche
Begriffe es in IT-Stellenanzeigen gibt, nicht welche auf jemanden
zutreffen. Es gehoert deshalb ins Repo; das daraus abgeleitete Profil
nicht.

Gesucht wird ohne Ruecksicht auf Gross- und Kleinschreibung. Wo das
gefaehrlich waere, schaltet ein eingebettetes (?-i:...) die Beachtung
wieder ein - "Go" als Sprache ist etwas anderes als "go" im Fliesstext.
"""
from __future__ import annotations

import re
from collections import Counter

SPRACHEN = "Programmiersprachen"
FRAMEWORKS = "Frameworks"
DATEN = "Daten"
CLOUD = "Cloud und Betrieb"
DATENBANKEN = "Datenbanken"
TESTEN = "Testen"
METHODEN = "Methoden"
SPRACHKENNTNISSE = "Sprachen"

# (Kategorie, Bezeichnung, Muster). Die Bezeichnung ist der Name, unter
# dem der Begriff in Profil und Tabelle erscheint - unabhaengig davon,
# wie die Anzeige ihn schreibt.
KATALOG: tuple[tuple[str, str, str], ...] = (
    (SPRACHEN, "Java", r"\bjava\b"),
    (SPRACHEN, "Python", r"\bpython\b"),
    (SPRACHEN, "JavaScript", r"\bjavascript\b|\becmascript\b|\bes6\b"),
    (SPRACHEN, "TypeScript", r"\btypescript\b"),
    (SPRACHEN, "SQL", r"\bsql\b"),
    (SPRACHEN, "Kotlin", r"\bkotlin\b"),
    (SPRACHEN, "Scala", r"\bscala\b"),
    # "Go" ohne Ruecksicht auf Schreibweise waere ein Griff ins Klo:
    # "go-live" und englisches "go" stehen in jeder zweiten Anzeige.
    (SPRACHEN, "Go", r"(?-i:\bGo\b)(?!\s*[-–]?\s*live)|\bgolang\b"),
    (SPRACHEN, "Rust", r"(?-i:\bRust\b)"),
    (SPRACHEN, "C#", r"\bc#|\bc-sharp\b|\bdotnet\b|\b\.net\b"),
    (SPRACHEN, "C++", r"\bc\+\+"),
    (SPRACHEN, "PHP", r"\bphp\b"),
    (SPRACHEN, "Bash", r"\bbash\b|\bshell[- ]?skript|\bpowershell\b"),
    (SPRACHEN, "R", r"(?-i:\bR\b)\s*(?:und|,|/)\s*(?-i:\bPython\b)|\br[- ]studio\b"),
    (FRAMEWORKS, "Spring", r"\bspring\b|\bspring[- ]boot\b"),
    (FRAMEWORKS, "React", r"\breact\b"),
    (FRAMEWORKS, "Angular", r"\bangular\b"),
    (FRAMEWORKS, "Vue", r"\bvue(?:\.js)?\b"),
    (FRAMEWORKS, "Node.js", r"\bnode(?:\.js)?\b"),
    (FRAMEWORKS, "Django", r"\bdjango\b"),
    (FRAMEWORKS, "FastAPI", r"\bfastapi\b"),
    (FRAMEWORKS, "Hibernate", r"\bhibernate\b|\bjpa\b"),
    (FRAMEWORKS, "Maven", r"\bmaven\b"),
    (FRAMEWORKS, "Gradle", r"\bgradle\b"),
    (FRAMEWORKS, "REST-APIs", r"\brest\b|\brestful\b|\bapi[- ]entwicklung\b"),
    (FRAMEWORKS, "GraphQL", r"\bgraphql\b"),
    (FRAMEWORKS, "Microservices", r"\bmicroservice|\bmikroservice"),
    (DATEN, "Kafka", r"\bkafka\b"),
    (DATEN, "Spark", r"\bspark\b|\bpyspark\b"),
    (DATEN, "Airflow", r"\bairflow\b"),
    (DATEN, "dbt", r"\bdbt\b"),
    (DATEN, "ETL", r"\betl\b|\belt\b|\bdatenpipeline|\bdata pipeline"),
    (DATEN, "Data Warehouse", r"\bdata[- ]warehouse|\bdwh\b|\bdata[- ]lake|\blakehouse\b"),
    (DATEN, "BigQuery", r"\bbigquery\b"),
    (DATEN, "Snowflake", r"\bsnowflake\b"),
    (DATEN, "Databricks", r"\bdatabricks\b"),
    (DATEN, "Pandas", r"\bpandas\b|\bnumpy\b"),
    (DATEN, "Machine Learning", r"\bmachine learning\b|\bmaschinelles lernen\b|\bml[- ]modell|\bdeep learning\b"),
    (DATEN, "Power BI", r"\bpower[- ]?bi\b"),
    (DATEN, "Tableau", r"\btableau\b"),
    (CLOUD, "AWS", r"\baws\b|\bamazon web services\b"),
    (CLOUD, "Azure", r"\bazure\b"),
    (CLOUD, "GCP", r"\bgcp\b|\bgoogle cloud\b"),
    (CLOUD, "Docker", r"\bdocker\b|\bcontainer\b"),
    (CLOUD, "Kubernetes", r"\bkubernetes\b|\bk8s\b|\bopenshift\b"),
    (CLOUD, "Terraform", r"\bterraform\b|\binfrastructure as code\b|\biac\b"),
    (CLOUD, "CI/CD", r"\bci[-/ ]?cd\b|\bcontinuous integration\b|\bcontinuous delivery\b"),
    (CLOUD, "GitLab", r"\bgitlab\b"),
    (CLOUD, "GitHub", r"\bgithub\b"),
    (CLOUD, "Jenkins", r"\bjenkins\b"),
    (CLOUD, "Git", r"\bgit\b|\bversionsverwaltung\b"),
    (CLOUD, "Linux", r"\blinux\b|\bunix\b"),
    (CLOUD, "Monitoring", r"\bmonitoring\b|\bgrafana\b|\bprometheus\b|\bobservability\b|\blogging\b"),
    (CLOUD, "Serverless", r"\bserverless\b|\blambda\b|\bcloud functions\b"),
    (DATENBANKEN, "PostgreSQL", r"\bpostgres|\bpostgresql\b"),
    (DATENBANKEN, "MySQL", r"\bmysql\b|\bmariadb\b"),
    (DATENBANKEN, "Oracle", r"\boracle\b"),
    (DATENBANKEN, "MongoDB", r"\bmongodb\b|\bmongo\b"),
    (DATENBANKEN, "Redis", r"\bredis\b"),
    (DATENBANKEN, "DynamoDB", r"\bdynamodb\b"),
    (DATENBANKEN, "Elasticsearch", r"\belasticsearch\b|\bopensearch\b"),
    (TESTEN, "JUnit", r"\bjunit\b"),
    (TESTEN, "Selenium", r"\bselenium\b"),
    (TESTEN, "Playwright", r"\bplaywright\b|\bcypress\b"),
    (TESTEN, "Testautomatisierung", r"\btestautomat|\bautomatisierte tests\b|\btest[- ]automation\b"),
    (TESTEN, "Unit-Tests", r"\bunit[- ]?tests?\b|\bmodultests?\b|\btdd\b"),
    (TESTEN, "Code Review", r"\bcode[- ]review|\bpull[- ]request|\bmerge[- ]request"),
    (METHODEN, "Scrum", r"\bscrum\b|\bsprint\b"),
    (METHODEN, "Agile Arbeitsweise", r"\bagil|\bkanban\b|\bsafe\b"),
    (METHODEN, "DevOps", r"\bdevops\b"),
    (METHODEN, "Jira", r"\bjira\b|\bconfluence\b"),
    (METHODEN, "Softwarearchitektur", r"\bsoftwarearchitektur|\barchitekturentwurf|\bverteilte systeme\b|\bclean code\b"),
    (METHODEN, "Anforderungsanalyse", r"\banforderungsanalyse|\brequirements engineering\b|\bfachkonzept"),
    (METHODEN, "Datenschutz", r"\bdsgvo\b|\bdatenschutz\b|\bgdpr\b"),
    (SPRACHKENNTNISSE, "Deutsch", r"\bdeutschkenntnisse\b|\bdeutsch\b"),
    (SPRACHKENNTNISSE, "Englisch", r"\benglischkenntnisse\b|\benglisch\b|\benglish\b"),
)

_UEBERSETZT = tuple(
    (kategorie, bezeichnung, re.compile(muster, re.IGNORECASE))
    for kategorie, bezeichnung, muster in KATALOG
)

KATEGORIE_VON = {bezeichnung: kategorie for kategorie, bezeichnung, _ in KATALOG}

# Bezeichnung -> fertiges Muster. Der Poller schlaegt hier nach, wenn ein
# Suchbegriff genau einen Katalogeintrag nennt: "Java" soll dann nicht
# ueber die Teilzeichenkette in "JavaScript" anschlagen, sondern ueber
# das gepruefte Muster java.
MUSTER_VON = {bezeichnung: muster for _, bezeichnung, muster in _UEBERSETZT}


def muster_fuer(bezeichnung: str):
    """Das Katalogmuster zu einer Bezeichnung, ohne Ruecksicht auf Schreibung."""
    gesucht = bezeichnung.strip().casefold()
    for name, muster in MUSTER_VON.items():
        if name.casefold() == gesucht:
            return muster
    return None


def finde(text: str) -> list[str]:
    """Alle Begriffe, die der Text nennt - in Katalogreihenfolge."""
    if not text:
        return []
    return [bezeichnung for _, bezeichnung, muster in _UEBERSETZT if muster.search(text)]


def haeufigkeiten(text: str) -> dict[str, int]:
    """Wie oft jeder Begriff vorkommt.

    Die Zahl trennt im Profil das Kerngeschaeft von der Randnotiz: was
    im Lebenslauf mehrfach auftaucht, steht meist auch im Zentrum der
    bisherigen Arbeit.
    """
    if not text:
        return {}
    gezaehlt = Counter()
    for _, bezeichnung, muster in _UEBERSETZT:
        anzahl = len(muster.findall(text))
        if anzahl:
            gezaehlt[bezeichnung] = anzahl
    return dict(gezaehlt)


def nach_kategorie(bezeichnungen: list[str]) -> dict[str, list[str]]:
    """Gruppiert fuer die Ausgabe, in Katalogreihenfolge."""
    gruppen: dict[str, list[str]] = {}
    for _, bezeichnung, _muster in _UEBERSETZT:
        if bezeichnung in bezeichnungen:
            gruppen.setdefault(KATEGORIE_VON[bezeichnung], []).append(bezeichnung)
    return gruppen
