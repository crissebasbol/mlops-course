import json
import random
from pathlib import Path

from locust import HttpUser, between, task

EXAMPLES = json.loads((Path(__file__).parent / "examples.json").read_text())
MUESTRAS = [sample for samples in EXAMPLES.values() for sample in samples]


class UsuarioDeCarga(HttpUser):
    wait_time = between(1, 2.5)

    @task
    def hacer_inferencia(self):
        with self.client.post(
            "/predict", json=random.choice(MUESTRAS), name="/predict", catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}: {response.text[:200]}")
                return

            try:
                body = response.json()
            except ValueError:
                response.failure("La respuesta no contiene JSON valido")
                return

            if "prediction" not in body:
                response.failure("La respuesta no trae la prediccion")
                return
            response.success()

