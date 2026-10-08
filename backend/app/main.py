import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api import auth, kartoteki, system, uwagi
from app.api import ustawienia as api_ustawienia
from app.config import KATALOG_BACKENDU, ustawienia

if sys.platform == "win32":
    # Lokalnie AVG podmienia certyfikaty HTTPS; bez tego pobranie certyfikatów Google
    # (weryfikacja tokenu) kończy się błędem SSL. Na serwerze (FreeBSD) nie działa.
    import truststore

    truststore.inject_into_ssl()

# Zbudowany frontend (npm run build) kopiowany przy wdrożeniu do backend/static.
KATALOG_FRONTU = KATALOG_BACKENDU / "static"


def utworz_aplikacje() -> FastAPI:
    u = ustawienia()
    aplikacja = FastAPI(
        title="Pluszek Księgowość",
        docs_url="/api/docs" if u.tryb_deweloperski else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if u.tryb_deweloperski else None,
    )
    if u.lista_cors:
        aplikacja.add_middleware(
            CORSMiddleware,
            allow_origins=u.lista_cors,
            allow_methods=["*"],
            allow_headers=["Authorization", "Content-Type"],
        )

    aplikacja.include_router(auth.router)
    aplikacja.include_router(system.router)
    aplikacja.include_router(uwagi.router)
    aplikacja.include_router(api_ustawienia.router)
    aplikacja.include_router(kartoteki.router)

    @aplikacja.get("/{sciezka:path}", include_in_schema=False)
    def frontend(sciezka: str) -> FileResponse:
        """Serwuje SPA: istniejący plik albo index.html (routing po stronie Reacta)."""
        if sciezka.startswith("api/") or sciezka == "api" or not KATALOG_FRONTU.is_dir():
            raise HTTPException(404, "Nie znaleziono")
        plik = (KATALOG_FRONTU / sciezka).resolve()
        if sciezka and plik.is_file() and plik.is_relative_to(KATALOG_FRONTU.resolve()):
            return FileResponse(plik)
        return FileResponse(KATALOG_FRONTU / "index.html")

    return aplikacja


app = utworz_aplikacje()
