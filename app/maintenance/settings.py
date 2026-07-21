from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    DATABASE_URL: str  # sync psycopg (worker)
    ASYNC_DATABASE_URL: str  # asyncpg (api)

    CMMS_BASE_URL: str
    CMMS_TOKEN: str

    INBOUND_API_KEY: SecretStr

    DATA_DIR: str = "./app/maintenance/prediction_out"  # helyi könyvtár is lehet

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
