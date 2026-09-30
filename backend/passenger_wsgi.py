"""Punkt wejścia dla Phusion Passenger (mydevil). Passenger mówi WSGI, FastAPI jest ASGI.

Układ na serwerze (wzorzec z ramiarz.eu):
    ~/domains/faktury.pluszek.pl/
        .venv/                         ← zależności (Python 3.11)
        backend/                       ← kod aplikacji + .env + static/ (zbudowany front)
        public_python/passenger_wsgi.py  ← TEN plik (kopiowany przez deploy.sh)
"""

import os
import sys

KATALOG_DOMENY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KATALOG_BACKENDU = os.path.join(KATALOG_DOMENY, "backend")

# Passenger uruchamia systemowy /usr/local/bin/python3.11. Jego globalne site-packages trzeba
# WYŁĄCZYĆ (tak jak robi to venv): jest tam stary Cython, przez który SQLAlchemy 2.1 wywraca się
# przy imporcie (ValueError w Cython/Shadow.py). Zostaje stdlib + pakiety z naszego venv.
sys.path[:] = [p for p in sys.path if "site-packages" not in p]
sys.path.insert(0, os.path.join(KATALOG_DOMENY, ".venv", "lib", "python3.11", "site-packages"))
sys.path.insert(0, KATALOG_BACKENDU)
os.chdir(KATALOG_BACKENDU)

from a2wsgi import ASGIMiddleware  # noqa: E402

from app.main import app  # noqa: E402

application = ASGIMiddleware(app)
