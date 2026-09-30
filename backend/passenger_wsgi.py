"""Punkt wejścia dla Phusion Passenger (mydevil). Passenger mówi WSGI, FastAPI jest ASGI."""

import os
import sys

KATALOG = os.path.dirname(os.path.abspath(__file__))
PYTHON_VENV = os.path.join(KATALOG, ".venv", "bin", "python3")

# Passenger startuje systemowym Pythonem — przełączamy się na interpreter z venv.
if os.path.exists(PYTHON_VENV) and sys.executable != PYTHON_VENV:
    os.execl(PYTHON_VENV, PYTHON_VENV, *sys.argv)

sys.path.insert(0, KATALOG)
os.chdir(KATALOG)

from a2wsgi import ASGIMiddleware  # noqa: E402

from app.main import app  # noqa: E402

application = ASGIMiddleware(app)
