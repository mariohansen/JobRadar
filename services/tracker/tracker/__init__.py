"""Bewerbungs-Tracker: verwaltet den Status der gefundenen Anzeigen."""

# Das gemeinsame Paket liegt neben den Diensten, nicht in ihnen: lokal
# unter services/, auf der Instanz unter /opt/jobradar/. In beiden
# Faellen zwei Ebenen ueber diesem Paket - deshalb genuegt derselbe
# Ausdruck fuer beides.
import sys as _sys
from pathlib import Path as _Path

_gemeinsam = _Path(__file__).resolve().parents[2] / "gemeinsam"
if _gemeinsam.is_dir() and str(_gemeinsam) not in _sys.path:
    _sys.path.insert(0, str(_gemeinsam))
