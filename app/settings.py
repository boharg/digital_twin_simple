from pydantic_settings import BaseSettings, SettingsConfigDict
import os

print("DEBUG DATABASE_URL:", os.getenv("DATABASE_URL"))

class Settings(BaseSettings):
    DATABASE_URL: str  # sync psycopg (worker)
    ASYNC_DATABASE_URL: str  # asyncpg (api)
    CMMS_BASE_URL: str
    CMMS_TOKEN: str
    DATA_DIR: str = "./prediction_out"  # helyi könyvtár is lehet

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
