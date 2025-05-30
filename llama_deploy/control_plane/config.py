from typing import List
from urllib.parse import urlparse

from llama_index.core.storage.kvstore.types import BaseKVStore
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ControlPlaneConfig(BaseSettings):
    """Control plane configuration."""

    model_config = SettingsConfigDict(
        env_prefix="CONTROL_PLANE_", arbitrary_types_allowed=True
    )

    services_store_key: str = Field(
        default="services",
        description="Key for the services store. Defaults to 'services'.",
    )
    tasks_store_key: str = Field(
        default="tasks",
        description="Key for the tasks store. Defaults to 'tasks'.",
    )
    session_store_key: str = Field(
        default="sessions",
        description="Key for the session store. Defaults to 'sessions'.",
    )
    step_interval: float = Field(
        default=0.1,
        description="The interval in seconds to poll for tool call results. Defaults to 0.1s.",
    )
    host: str = Field(
        default="127.0.0.1",
        description="The host where to run the control plane server",
    )
    port: int = Field(
        default=8000, description="The TCP port where to bind the control plane server"
    )
    internal_host: str | None = None
    internal_port: int | None = None
    running: bool = True
    cors_origins: List[str] | None = Field(
        default=None,
        description="List of hosts from which the service will accept CORS requests. Use ['*'] for all hosts.",
    )
    topic_namespace: str = Field(
        default="llama_deploy",
        description="The prefix used in the message queue topic to namespace messages from this control plane",
    )
    state_store_uri: str | None = Field(
        default=None,
        description="The connection URI of the database where to store state. If None, SimpleKVStore will be used",
    )
    use_tls: bool = Field(
        default=False,
        description="Use TLS (HTTPS) to communicate with the control plane",
    )

    @property
    def url(self) -> str:
        if self.use_tls:
            return f"https://{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"


def parse_state_store_uri(uri: str) -> BaseKVStore:
    bits = urlparse(uri)

    # Redis supports multiple schemes:
    # https://redis-py.readthedocs.io/en/stable/connections.html#redis.Redis.from_url
    if bits.scheme in {"redis", "rediss", "unix"}:
        try:
            from llama_index.storage.kvstore.redis import RedisKVStore  # type: ignore

            return RedisKVStore(redis_uri=uri)
        except ImportError:
            msg = (
                "key-value store redis is not available, please install the required "
                "llama_index integration with 'pip install llama-index-storage-kvstore-redis'."
            )
            raise ValueError(msg)
    elif bits.scheme == "mongodb+srv":
        try:
            from llama_index.storage.kvstore.mongodb import (  # type:ignore
                MongoDBKVStore,
            )

            return MongoDBKVStore(uri=uri)
        except ImportError:
            msg = (
                f"key-value store {bits.scheme} is not available, please install the required "
                "llama_index integration with 'pip install llama-index-storage-kvstore-mongodb'."
            )
            raise ValueError(msg)
    else:
        msg = f"key-value store '{bits.scheme}' is not supported."
        raise ValueError(msg)
