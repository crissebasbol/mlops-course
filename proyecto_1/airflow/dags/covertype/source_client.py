from dataclasses import dataclass

import requests

from .config import (
    DATA_SOURCE_MODE,
    DATA_TIMEOUT_SECONDS,
    GROUP_NUMBER,
    LOCAL_API_URL,
    REMOTE_API_URL,
    STATUS_TIMEOUT_SECONDS,
)

REMOTE = "remote"
LOCAL = "local"


class CollectionExhausted(Exception):
    """La API respondio 400: ya entrego todos los batches del grupo."""


@dataclass
class DataSource:
    name: str       # remote | local
    base_url: str


@dataclass
class BatchResponse:
    group_number: int
    batch_number: int
    rows: list[list[str]]

class DataSourceClient:
    """Consigue la Data API (la remota o la replica source_app)"""

    def __init__(self, source: DataSource, group_number: int = GROUP_NUMBER):
        self.source = source
        self.group_number = group_number

    @staticmethod
    def is_available(base_url: str) -> bool:
        """Consulta el endpoint de status"""
        try:
            respuesta = requests.get(f"{base_url}/", timeout=STATUS_TIMEOUT_SECONDS)
            return respuesta.status_code == 200
        except requests.RequestException as exc:
            print(f"{base_url} no responde: {exc}")
            return False

    @classmethod
    def resolve(cls, mode: str = DATA_SOURCE_MODE) -> DataSource:
        remoto = DataSource(REMOTE, REMOTE_API_URL)
        local = DataSource(LOCAL, LOCAL_API_URL)

        if mode == REMOTE:
            return remoto
        if mode == LOCAL:
            return local
        if mode != "auto":
            raise ValueError(f"DATA_SOURCE_MODE invalido: '{mode}' (auto | remote | local)")

        if cls.is_available(remoto.base_url):
            return remoto
        print(f"Host remoto {remoto.base_url} no disponible, se usa source_app ({local.base_url})")
        if not cls.is_available(local.base_url):
            raise RuntimeError("Ni el host remoto ni source_app estan disponibles")
        return local

    def fetch_batch(self) -> BatchResponse:
        respuesta = requests.get(
            f"{self.source.base_url}/data",
            params={"group_number": self.group_number},
            timeout=DATA_TIMEOUT_SECONDS,
        )
        if respuesta.status_code == 400:
            raise CollectionExhausted(respuesta.text)
        respuesta.raise_for_status()

        cuerpo = respuesta.json()
        return BatchResponse(
            group_number=int(cuerpo["group_number"]),
            batch_number=int(cuerpo["batch_number"]),
            rows=cuerpo["data"],
        )

    def restart(self) -> None:
        respuesta = requests.get(
            f"{self.source.base_url}/restart_data_generation",
            params={"group_number": self.group_number},
            timeout=STATUS_TIMEOUT_SECONDS * 2,
        )
        respuesta.raise_for_status()
