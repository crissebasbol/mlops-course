import io
import json
import re
from datetime import datetime, timezone

import joblib
from minio import Minio

from .config import (
    MINIO_ACCESS_KEY,
    MINIO_BUCKET,
    MINIO_ENDPOINT,
    MINIO_SECRET_KEY,
    MINIO_SECURE,
)

VERSION_PATTERN = re.compile(r"^v(\d+)/(.+)$")
MODEL_OBJECT = "model.pkl"
METADATA_OBJECT = "metadata.json"


class ModelRegistry:
    """Modelos versionados en MinIO"""

    def __init__(self, bucket: str = MINIO_BUCKET):
        self.bucket = bucket
        self.client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def _scan(self, model_type: str) -> dict[int, set[str]]:
        versiones: dict[int, set[str]] = {}
        for obj in self.client.list_objects(self.bucket, prefix=f"{model_type}/", recursive=True):
            if m := VERSION_PATTERN.match(obj.object_name.removeprefix(f"{model_type}/")):
                versiones.setdefault(int(m.group(1)), set()).add(m.group(2))
        return versiones

    def list_versions(self, model_type: str) -> list[int]:
        return sorted(v for v, archivos in self._scan(model_type).items() if METADATA_OBJECT in archivos)

    def has_model(self, model_type: str) -> bool:
        if not self.client.bucket_exists(self.bucket):
            return False
        return bool(self.list_versions(model_type))

    def _put(self, nombre: str, datos: bytes, content_type: str) -> None:
        self.client.put_object(
            self.bucket, nombre, io.BytesIO(datos), length=len(datos), content_type=content_type
        )

    def save(self, model_type: str, payload: dict, metadata: dict) -> dict:
        """Sube el modelo como la siguiente version y devuelve su metadata."""
        self.ensure_bucket()
        versiones = self._scan(model_type)
        version = (max(versiones) + 1) if versiones else 1
        prefijo = f"{model_type}/v{version}"

        buffer = io.BytesIO()
        joblib.dump(payload, buffer)
        modelo = buffer.getvalue()

        metadata = {
            "model_type": model_type,
            "version": version,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "size_bytes": len(modelo),
            **metadata,
        }

        self._put(f"{prefijo}/{MODEL_OBJECT}", modelo, "application/octet-stream")
        self._put(
            f"{prefijo}/{METADATA_OBJECT}",
            json.dumps(metadata, indent=2, default=str).encode("utf-8"),
            "application/json",
        )
        print(f"Modelo guardado en s3://{self.bucket}/{prefijo}/ ({len(modelo) / 1e6:.1f} MB)")
        return metadata
