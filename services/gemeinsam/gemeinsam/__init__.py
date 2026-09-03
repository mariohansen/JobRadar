"""Gemeinsamer Code mehrerer Dienste.

Hier liegt, was mehr als ein Dienst braucht und was deshalb nirgends
zweimal stehen soll:

* faehigkeiten - Verzeichnis fachlicher Begriffe,
* profil       - das eigene Faehigkeitsprofil,
* passung      - der Abgleich zwischen beidem,
* jobdetail    - Abruf der Anzeigentexte.

Genutzt wird es vom `filter-dedup` auf der Instanz, der neue Anzeigen
anreichert und bewertet, und vom `tracker` auf dem eigenen Rechner, der
exportiert und auswertet.
"""
