from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

KATALOG_BACKENDU = Path(__file__).resolve().parent.parent


class Ustawienia(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=KATALOG_BACKENDU / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: str = "production"
    # Brak domyślnej wartości celowo: bez bazy aplikacja ma nie wstać (lekcja z RAMIARZ —
    # cicha domyślka startowała na pustej bazie i przyjmowała zapisy do „bazy-widma”).
    database_url: str
    database_url_test: str | None = None
    firebase_project_id: str = ""
    cors_origins: str = ""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Własny .env ma pierwszeństwo przed zmiennymi środowiska: na współdzielonym
        # hostingu inne aplikacje eksportują swoje zmienne w .bash_profile i potrafią
        # „wyciec” do tej aplikacji (lekcja z RAMIARZ).
        return init_settings, dotenv_settings, env_settings, file_secret_settings

    @property
    def tryb_deweloperski(self) -> bool:
        return self.environment.strip().lower() == "development"

    @property
    def lista_cors(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def ustawienia() -> Ustawienia:
    return Ustawienia()
