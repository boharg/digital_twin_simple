from pydantic_settings import BaseSettings, SettingsConfigDict
import os

print("DEBUG DATABASE_URL:", os.getenv("DATABASE_URL"))


class Settings(BaseSettings):
    DATABASE_URL: str  # sync psycopg (worker)
    ASYNC_DATABASE_URL: str  # asyncpg (api)
    CMMS_BASE_URL: str
    CMMS_TOKEN: str
    DATA_DIR: str = "./prediction_out"  # helyi könyvtár is lehet

    #
    MQTT_BROKER_HOST: str
    MQTT_BROKER_PORT: int
    MQTT_KEEPALIVE_INTERVAL: int
    MQTT_TOPIC_TO_SUBSCRIBE: str
    MQTT_USERNAME: str
    MQTT_PASSWORD: str

    DB_NAME: str
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    # asyncpg pool konfiguracio
    DB_POOL_MIN_SIZE: int
    DB_POOL_MAX_SIZE: int

    # backpressure a feldolgozo queue-ra
    QUEUE_MAXSIZE: int

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
