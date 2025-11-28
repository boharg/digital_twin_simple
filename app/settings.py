from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from typing import Dict

print("DEBUG DATABASE_URL:", os.getenv("DATABASE_URL"))


class Settings(BaseSettings):
    DATABASE_URL: str  # sync psycopg (worker)
    ASYNC_DATABASE_URL: str  # asyncpg (api)
    CMMS_BASE_URL: str
    CMMS_TOKEN: str
    DATA_DIR: str = "./prediction_out"  # helyi könyvtár is lehet

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


class DAQ_Settings(BaseSettings):
    #
    SENSOR_CONFIG: Dict[str, Dict[str, str]] = {
        "S2.1": {"id": "1db52ee7-974f-4bd9-8d29-04e9a2a839fc", "time_key": "S2.1_t"},
        "S2.2": {"id": "bb75e358-9749-4012-96e9-d1f95c73c838", "time_key": "S2.2_t"},
        "S2.3": {"id": "43763fbd-823e-4928-8a9d-25a5d1796ba3", "time_key": "S2.3_t"},
        "S2.4": {"id": "414e03a4-5d3f-4df3-bd51-70f02852c705", "time_key": "S2.4_t"},
        "S2.5": {"id": "94a3d026-b9e6-45cc-aaec-ee8e1a3d86e5", "time_key": "S2.5_t"},
        "S2.6": {"id": "0765dc00-4a04-405b-a59d-a06fc07ff7bd", "time_key": "S2.6_t"},
        "S2.7": {"id": "-", "time_key": "S2.7_t"},
        "S2.8": {"id": "-", "time_key": "S2.8_t"},
        "adc1": {"id": "ad3146a4-a47b-4ad5-aa19-f4ce9ee99204", "time_key": "adc1_t"},
        "S1.1": {"id": "40f227f0-df30-4ab6-952e-31b5967b0c42", "time_key": "S1.1_t"},
        "S1.2": {"id": "a6c5a417-31e8-4cbd-93f2-bc992001ced0", "time_key": "S1.2_t"},
        "S1.3": {"id": "754114d5-3c04-4926-9c53-3f3739fc5b48", "time_key": "S1.3_t"},
        "S1.4": {"id": "755d6aa7-e60d-46d9-b5a0-64ba743d8922", "time_key": "S1.4_t"},
        "S1.5": {"id": "f712012b-d611-4f52-be1b-ed9599119183", "time_key": "S1.5_t"},
        "S1.6": {"id": "4b7a0a49-1fdd-4e67-8578-f419c6a96fd7", "time_key": "S1.6_t"},
    }

    MQTT_BROKER_HOST = "192.168.130.182"
    MQTT_BROKER_PORT = 1883
    MQTT_KEEPALIVE_INTERVAL = 60
    MQTT_TOPIC_TO_SUBSCRIBE = "daq"
    MQTT_USERNAME = "operator"
    MQTT_PASSWORD = "operator"

    DB_NAME = "postgres"
    DB_HOST = "192.168.130.156"
    DB_PORT = 5432
    DB_USER = "technical_user"
    DB_PASSWORD = "technical"
    # asyncpg pool konfiguracio
    DB_POOL_MIN_SIZE = 1
    DB_POOL_MAX_SIZE = 5

    # backpressure a feldolgozo queue-ra
    QUEUE_MAXSIZE = 1000


settings = Settings()
daq_settings = DAQ_Settings()
