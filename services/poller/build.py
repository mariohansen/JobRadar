"""Baut das Deployment-Paket der Poller-Lambda.

Gebaut wird moeglicherweise unter Windows, ausgefuehrt wird auf Linux.
confluent-kafka bringt kompiliertes librdkafka mit - ein lokal
installiertes Paket waere in der Lambda unbrauchbar und scheitert dort
beim Import. Die Abhaengigkeiten werden deshalb gezielt als Linux-Wheels
geholt, statt die lokale Installation zu kopieren.

Aufruf: python services/poller/build.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HIER = Path(__file__).parent
BUILD = HIER / "build"
PAKET = HIER / "poller.zip"

# Muss zur Laufzeit der Lambda passen, sonst passen die Wheels nicht.
PYTHON_VERSION = "3.13"
# manylinux_2_28 verlangt glibc 2.28 oder neuer. Die Lambda-Laufzeit
# basiert auf Amazon Linux 2023 mit glibc 2.34, passt also. Das aeltere
# manylinux2014 wird von confluent-kafka nicht mehr bedient.
PLATTFORM = "manylinux_2_28_x86_64"

# boto3 fehlt hier bewusst: die Lambda-Laufzeit bringt es mit. Mitpacken
# wuerde das Paket um mehrere Megabyte aufblaehen, ohne etwas zu aendern.
ABHAENGIGKEITEN = ["confluent-kafka>=2.6,<3"]


def leere_build_verzeichnis() -> None:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)


def installiere_abhaengigkeiten() -> None:
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "--target", str(BUILD),
            # Ohne diese vier Angaben nimmt pip die Wheels der laufenden
            # Plattform - unter Windows also welche, die in der Lambda
            # nicht laden.
            "--platform", PLATTFORM,
            "--implementation", "cp",
            "--python-version", PYTHON_VERSION,
            "--only-binary=:all:",
            # Ohne dies legt pip .pyc-Dateien an. Die tragen Zeitstempel,
            # womit das Paket bei jedem Bau eine andere Pruefsumme
            # bekaeme. Python kompiliert zur Laufzeit selbst nach.
            "--no-compile",
            "--quiet",
            *ABHAENGIGKEITEN,
        ],
        check=True,
    )


def kopiere_quellcode() -> None:
    ohne_muell = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(HIER / "poller", BUILD / "poller", ignore=ohne_muell)
    # Der Poller berechnet den inhaltlichen Fingerabdruck mit demselben
    # Code wie der filter-dedup. Liefe hier eine eigene Kopie mit, fielen
    # beide nach der ersten einseitigen Aenderung auseinander - und die
    # Deduplizierung ueber Quellen hinweg waere lautlos kaputt.
    shutil.copytree(
        HIER.parent / "gemeinsam" / "gemeinsam",
        BUILD / "gemeinsam",
        ignore=ohne_muell,
    )


def schnuere_paket() -> None:
    """Erzeugt ein reproduzierbares ZIP.

    Fester Zeitstempel und sortierte Reihenfolge sorgen dafuer, dass
    gleicher Inhalt dieselbe Pruefsumme ergibt. Sonst sieht Terraform bei
    jedem Build eine Aenderung und rollt die Lambda ohne Grund neu aus.
    """
    if PAKET.exists():
        PAKET.unlink()

    dateien = sorted(
        p for p in BUILD.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    )
    with zipfile.ZipFile(PAKET, "w", zipfile.ZIP_DEFLATED) as archiv:
        for datei in dateien:
            eintrag = zipfile.ZipInfo(
                str(datei.relative_to(BUILD)).replace("\\", "/"),
                date_time=(1980, 1, 1, 0, 0, 0),
            )
            eintrag.external_attr = 0o644 << 16
            eintrag.compress_type = zipfile.ZIP_DEFLATED
            archiv.writestr(eintrag, datei.read_bytes())


def main() -> int:
    leere_build_verzeichnis()
    installiere_abhaengigkeiten()
    kopiere_quellcode()
    schnuere_paket()
    groesse_mb = PAKET.stat().st_size / 1024 / 1024
    print(f"{PAKET.name}: {groesse_mb:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
