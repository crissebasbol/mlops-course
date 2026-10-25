import io
import tempfile

import pandas as pd
import requests
from minio import Minio

from .config import DATASETS_BUCKET, MINIO_ACCESS_KEY, MINIO_ENDPOINT, MINIO_SECRET_KEY, SOURCE_COLUMNS


class DatasetStorage:
    """Archivo fuente y snapshots de los splits en el bucket `datasets` de MinIO."""

    def __init__(self):
        self.client = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)
        if not self.client.bucket_exists(DATASETS_BUCKET):
            self.client.make_bucket(DATASETS_BUCKET)

    def exists(self, object_name: str) -> bool:
        try:
            self.client.stat_object(DATASETS_BUCKET, object_name)
            return True
        except Exception:
            return False

    def download_source(self, url: str, object_name: str) -> None:
        """Descarga el CSV desde la URL del enunciado y lo sube a MinIO."""
        with tempfile.NamedTemporaryFile(suffix=".csv") as tmp:
            with requests.get(url, stream=True, allow_redirects=True, timeout=300) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=1 << 20):
                    tmp.write(chunk)
            tmp.flush()
            tmp.seek(0)
            header = tmp.readline().decode("utf-8", errors="replace").lstrip("\ufeff").strip().split(",")
            if header != SOURCE_COLUMNS:
                raise ValueError(f"La descarga no es el CSV esperado. Encabezado recibido: {header[:5]}...")
            self.client.fput_object(DATASETS_BUCKET, object_name, tmp.name, content_type="text/csv")

    def read_csv(self, object_name: str) -> pd.DataFrame:
        """Lee el CSV como texto, sin convertir '?' ni 'None' a nulos."""
        response = self.client.get_object(DATASETS_BUCKET, object_name)
        try:
            return pd.read_csv(io.BytesIO(response.read()), dtype=str, keep_default_na=False)
        finally:
            response.close()
            response.release_conn()

    def put_parquet(self, df: pd.DataFrame, object_name: str) -> None:
        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False)
        size = buffer.tell()
        buffer.seek(0)
        self.client.put_object(DATASETS_BUCKET, object_name, buffer, size, content_type="application/octet-stream")

    def get_parquet(self, object_name: str) -> pd.DataFrame:
        response = self.client.get_object(DATASETS_BUCKET, object_name)
        try:
            return pd.read_parquet(io.BytesIO(response.read()))
        finally:
            response.close()
            response.release_conn()
