from functools import lru_cache

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    # hide_input_in_errors: sin esto, el error de validación imprime todos los
    # valores recibidos, incluida la contraseña de la base.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        hide_input_in_errors=True,
    )

    # Base de datos
    POSTGRES_USER: str = "postgres"
    # Secreto sin valor por defecto: si falta, la aplicación no arranca.
    POSTGRES_PASSWORD: SecretStr = Field(min_length=1)
    POSTGRES_DB: str = "taller"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = Field(default=5432, ge=1, le=65535)
    DB_POOL_SIZE: int = Field(default=10, ge=1)
    SQL_ECHO: bool = False

    # Seguridad
    # Secreto sin valor por defecto. El mínimo rechaza una clave vacía o un marcador sin completar.
    SECRET_KEY: SecretStr = Field(min_length=32)
    BCRYPT_COST: int = Field(default=12, ge=4, le=31)
    TOKEN_DURACION_SEGUNDOS: int = Field(default=1800, gt=0)
    COOKIE_SECURE: bool = True

    # repr=False: la URL lleva la contraseña y no tiene que aparecer al imprimir Settings.
    @computed_field(repr=False)
    @property
    def DATABASE_URL(self) -> str:
        # URL.create escapa los caracteres especiales de la contraseña, como @ o /.
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)


# Se lee recién cuando alguien la pide, no al importar este módulo, y una sola vez.
@lru_cache
def get_settings() -> Settings:
    return Settings()
