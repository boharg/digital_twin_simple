import asyncio
import json
from contextlib import suppress
from datetime import datetime
from typing import Any, Optional
from pathlib import Path

import asyncpg
from asyncio_mqtt import Client, MqttError

from .settings import settings


INSERT_SQL = "INSERT INTO measurements (value, time, sensor_id) VALUES ($1, $2, $3);"

sensor_config = json.loads(Path("sensor_config.json").read_text(encoding="utf-8"))


def _parse_timestamp(raw: Any) -> datetime:
    """Best-effort ISO timestamp parsing with UTC fallback."""
    if raw is None:
        return datetime.utcnow()
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return datetime.utcnow()


class AsyncIngestService:
    """Aszinkron MQTT -> TimescaleDB rogzito szolgaltatas."""

    def __init__(self, mqtt_topic: Optional[str] = None) -> None:
        self.mqtt_topic = mqtt_topic or settings.MQTT_TOPIC_TO_SUBSCRIBE
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=settings.QUEUE_MAXSIZE)
        self.pool: Optional[asyncpg.Pool] = None
        self.client = Client(
            hostname=settings.MQTT_BROKER_HOST,
            port=settings.MQTT_BROKER_PORT,
            username=settings.MQTT_USERNAME or None,
            password=settings.MQTT_PASSWORD or None,
            keepalive=settings.MQTT_KEEPALIVE_INTERVAL,
        )
        self._db_worker_task: Optional[asyncio.Task] = None

    async def _init_pool(self) -> None:
        self.pool = await asyncpg.create_pool(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            min_size=settings.DB_POOL_MIN_SIZE,
            max_size=settings.DB_POOL_MAX_SIZE,
        )
        print("Async DB pool opened.")

    async def run(self) -> None:
        """Inditja a teljes fogyaszto lancot (MQTT + DB worker)."""
        await self._init_pool()
        self._db_worker_task = asyncio.create_task(self._db_worker(), name="db-writer")
        try:
            await self._consume_mqtt()
        finally:
            await self.shutdown()

    async def _consume_mqtt(self) -> None:
        try:
            async with self.client as client:
                async with client.unfiltered_messages() as messages:
                    await client.subscribe(self.mqtt_topic)
                    print(f"Feliratkozva a topicra: {self.mqtt_topic}")
                    async for message in messages:
                        await self._handle_raw_message(message.topic, message.payload)
        except MqttError as exc:
            print(f"MQTT hiba: {exc}")

    async def _handle_raw_message(self, topic: str, payload: bytes) -> None:
        try:
            payload_str = payload.decode("utf-8")
            data = json.loads(payload_str)
        except json.JSONDecodeError:
            print(f"Rossz JSON: {payload}")
            return
        except UnicodeDecodeError:
            print(f"Nem UTF-8 payload: {payload}")
            return

        for key, cfg in sensor_config.items():
            if key not in data or not cfg.get("id"):
                continue
            timestamp_raw = data.get(cfg["time_key"])
            timestamp = _parse_timestamp(timestamp_raw)
            measurement = (str(data[key]), timestamp, cfg["id"])
            try:
                self.queue.put_nowait(measurement)
            except asyncio.QueueFull:
                print("Feldolgozasi sor tele, uzenet eldobva.")

    async def _db_worker(self) -> None:
        while True:
            value, timestamp, sensor_id = await self.queue.get()
            try:
                if not self.pool:
                    raise RuntimeError("Adatbazis pool nincs inicializalva.")
                async with self.pool.acquire() as conn:
                    await conn.execute(INSERT_SQL, value, timestamp, sensor_id)
            except Exception as exc:
                print(f"DB irasi hiba: {exc}")
            finally:
                self.queue.task_done()

    async def shutdown(self) -> None:
        if self._db_worker_task:
            self._db_worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._db_worker_task
        if self.pool:
            await self.pool.close()
        with suppress(Exception):
            await self.client.disconnect()
