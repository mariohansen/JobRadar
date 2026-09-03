"""Luftlinie zwischen zwei deutschen Staedten, ohne Netzzugriff.

Die Jobsuche der Bundesagentur liefert die Entfernung mit - allerdings
nur im ortsgebundenen Durchgang. Die uebrigen Boersen liefern gar keine;
dort steht nur ein Ortsname. Fuer die Spalte "Entfernung (km)" hiesse das
bei jeder zweiten Anzeige eine leere Zelle.

Statt eines vollstaendigen Postleitzahlenverzeichnisses (rund achttausend
Eintraege, mehrere Megabyte) steht hier eine Liste der groessten Staedte.
Stellenanzeigen nennen fast immer eine davon; was nicht darin steht,
bekommt eben keine Entfernung - eine leere Zelle ist besser als eine
falsche Zahl.

Gerechnet wird die Luftlinie ueber die Haversine-Formel. Die tatsaechliche
Fahrstrecke ist laenger, aber fuer die Frage "kommt das ueberhaupt in
Frage" reicht die Groessenordnung, und sie ist ohne Kartendienst zu
haben.
"""
from __future__ import annotations

import math
import re

# Ort -> (Breite, Laenge). Die 100 groessten Staedte Deutschlands sowie
# das Hamburger Umland, weil dort der Suchradius liegt.
STAEDTE: dict[str, tuple[float, float]] = {
    "berlin": (52.520, 13.405),
    "hamburg": (53.551, 9.993),
    "münchen": (48.135, 11.582),
    "köln": (50.937, 6.960),
    "frankfurt am main": (50.110, 8.682),
    "stuttgart": (48.776, 9.183),
    "düsseldorf": (51.228, 6.773),
    "leipzig": (51.340, 12.375),
    "dortmund": (51.514, 7.466),
    "essen": (51.456, 7.012),
    "bremen": (53.079, 8.802),
    "dresden": (51.051, 13.738),
    "hannover": (52.376, 9.732),
    "nürnberg": (49.452, 11.077),
    "duisburg": (51.434, 6.763),
    "bochum": (51.482, 7.216),
    "wuppertal": (51.256, 7.150),
    "bielefeld": (52.030, 8.532),
    "bonn": (50.737, 7.098),
    "münster": (51.960, 7.626),
    "karlsruhe": (49.007, 8.404),
    "mannheim": (49.488, 8.469),
    "augsburg": (48.371, 10.898),
    "wiesbaden": (50.083, 8.240),
    "mönchengladbach": (51.180, 6.442),
    "gelsenkirchen": (51.517, 7.086),
    "braunschweig": (52.269, 10.521),
    "chemnitz": (50.828, 12.921),
    "kiel": (54.323, 10.135),
    "aachen": (50.776, 6.084),
    "halle": (51.483, 11.970),
    "magdeburg": (52.121, 11.628),
    "freiburg im breisgau": (47.999, 7.842),
    "krefeld": (51.334, 6.564),
    "lübeck": (53.866, 10.687),
    "oberhausen": (51.470, 6.851),
    "erfurt": (50.985, 11.030),
    "mainz": (49.993, 8.247),
    "rostock": (54.093, 12.099),
    "kassel": (51.312, 9.480),
    "hagen": (51.361, 7.472),
    "potsdam": (52.391, 13.064),
    "saarbrücken": (49.240, 6.997),
    "hamm": (51.680, 7.821),
    "ludwigshafen am rhein": (49.481, 8.446),
    "oldenburg": (53.144, 8.214),
    "mülheim an der ruhr": (51.427, 6.883),
    "osnabrück": (52.279, 8.047),
    "leverkusen": (51.033, 6.985),
    "heidelberg": (49.399, 8.672),
    "darmstadt": (49.873, 8.651),
    "solingen": (51.171, 7.084),
    "regensburg": (49.013, 12.101),
    "herne": (51.538, 7.220),
    "paderborn": (51.719, 8.754),
    "neuss": (51.198, 6.686),
    "ingolstadt": (48.766, 11.425),
    "offenbach am main": (50.096, 8.776),
    "fürth": (49.478, 10.989),
    "würzburg": (49.792, 9.954),
    "ulm": (48.401, 9.987),
    "heilbronn": (49.143, 9.211),
    "pforzheim": (48.891, 8.698),
    "wolfsburg": (52.423, 10.786),
    "göttingen": (51.534, 9.936),
    "bottrop": (51.524, 6.923),
    "reutlingen": (48.492, 9.204),
    "koblenz": (50.357, 7.594),
    "bremerhaven": (53.540, 8.580),
    "recklinghausen": (51.614, 7.198),
    "bergisch gladbach": (50.992, 7.133),
    "erlangen": (49.590, 11.005),
    "jena": (50.928, 11.589),
    "remscheid": (51.180, 7.193),
    "trier": (49.750, 6.638),
    "salzgitter": (52.155, 10.334),
    "moers": (51.452, 6.626),
    "siegen": (50.876, 8.024),
    "hildesheim": (52.155, 9.951),
    "cottbus": (51.756, 14.333),
    "gütersloh": (51.907, 8.379),
    "kaiserslautern": (49.444, 7.769),
    "schwerin": (53.636, 11.401),
    "witten": (51.443, 7.352),
    "gera": (50.881, 12.082),
    "iserlohn": (51.374, 7.700),
    "ludwigsburg": (48.897, 9.192),
    "esslingen am neckar": (48.740, 9.310),
    "zwickau": (50.718, 12.496),
    "düren": (50.804, 6.493),
    "flensburg": (54.782, 9.434),
    "ratingen": (51.297, 6.849),
    "lünen": (51.616, 7.529),
    "villingen-schwenningen": (48.061, 8.494),
    "konstanz": (47.664, 9.175),
    "worms": (49.634, 8.354),
    "marburg": (50.802, 8.766),
    "dessau-roßlau": (51.831, 12.246),
    "wolfenbüttel": (52.163, 10.537),
    # Hamburger Umland - dort liegt der Suchradius, deshalb feiner.
    "norderstedt": (53.707, 9.981),
    "pinneberg": (53.660, 9.799),
    "wedel": (53.583, 9.708),
    "ahrensburg": (53.675, 10.240),
    "reinbek": (53.516, 10.250),
    "geesthacht": (53.436, 10.377),
    "elmshorn": (53.754, 9.653),
    "buxtehude": (53.472, 9.700),
    "stade": (53.594, 9.476),
    "buchholz in der nordheide": (53.328, 9.878),
    "seevetal": (53.400, 10.000),
    "winsen": (53.358, 10.212),
    "lüneburg": (53.247, 10.414),
    "henstedt-ulzburg": (53.786, 9.972),
    "quickborn": (53.729, 9.898),
    "schenefeld": (53.607, 9.827),
    "glinde": (53.542, 10.213),
    "bargteheide": (53.729, 10.257),
    "tornesch": (53.700, 9.720),
    "uetersen": (53.688, 9.665),
    "halstenbek": (53.632, 9.851),
    "rellingen": (53.648, 9.816),
    "barsbüttel": (53.564, 10.212),
    "wentorf": (53.492, 10.245),
}

ERDRADIUS_KM = 6371.0

# Zusaetze, die einem Ortsnamen in Stellenanzeigen anhaengen.
ZUSATZ = re.compile(
    r"\b(?:deutschland|germany|de|bei|bzw|und umgebung|umgebung|region|raum|kreis)\b",
    re.IGNORECASE,
)
PLZ = re.compile(r"\b\d{4,5}\b")
NICHT_WORT = re.compile(r"[^\w\s-]", re.UNICODE)


def normalisiere(ort: str) -> str:
    """Ortsname in der Form, in der die Tabelle ihn fuehrt."""
    if not isinstance(ort, str):
        return ""
    # Alles ab dem ersten Komma ist Land oder Bundesland.
    vorn = ort.split(",")[0]
    ohne_plz = PLZ.sub(" ", vorn)
    ohne_zusatz = ZUSATZ.sub(" ", ohne_plz)
    sauber = NICHT_WORT.sub(" ", ohne_zusatz)
    return " ".join(sauber.split()).casefold()


def koordinaten(ort: str) -> tuple[float, float] | None:
    """Breite und Laenge eines Ortes, oder None wenn unbekannt."""
    name = normalisiere(ort)
    if not name:
        return None
    if name in STAEDTE:
        return STAEDTE[name]
    # "Frankfurt" statt "Frankfurt am Main", "Halle (Saale)" statt "Halle".
    for bekannt, punkt in STAEDTE.items():
        if bekannt.startswith(name + " ") or name.startswith(bekannt + " "):
            return punkt
    return None


def luftlinie(von: tuple[float, float], nach: tuple[float, float]) -> float:
    """Entfernung zweier Koordinaten in Kilometern (Haversine)."""
    breite1, laenge1 = math.radians(von[0]), math.radians(von[1])
    breite2, laenge2 = math.radians(nach[0]), math.radians(nach[1])
    d_breite = breite2 - breite1
    d_laenge = laenge2 - laenge1
    a = (
        math.sin(d_breite / 2) ** 2
        + math.cos(breite1) * math.cos(breite2) * math.sin(d_laenge / 2) ** 2
    )
    return 2 * ERDRADIUS_KM * math.asin(math.sqrt(a))


def zwischen(von: str, nach: str) -> float | None:
    """Luftlinie zwischen zwei Ortsnamen, gerundet - oder None.

    None heisst: mindestens einer der beiden steht nicht in der Liste.
    Dann bleibt die Zelle leer, statt eine erfundene Zahl zu zeigen.
    """
    a, b = koordinaten(von), koordinaten(nach)
    if a is None or b is None:
        return None
    return round(luftlinie(a, b), 1)
