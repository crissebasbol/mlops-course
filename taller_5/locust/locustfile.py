import random

from locust import HttpUser, between, task

MUESTRAS = [
    {
        "elevation": 2596, "aspect": 51, "slope": 3,
        "horizontal_distance_to_hydrology": 258, "vertical_distance_to_hydrology": 0,
        "horizontal_distance_to_roadways": 510, "hillshade_9am": 221, "hillshade_noon": 232,
        "hillshade_3pm": 148, "horizontal_distance_to_fire_points": 6279,
        "wilderness_area": "Rawah", "soil_type": "C7745",
    },
    {
        "elevation": 2804, "aspect": 139, "slope": 9,
        "horizontal_distance_to_hydrology": 268, "vertical_distance_to_hydrology": 65,
        "horizontal_distance_to_roadways": 3180, "hillshade_9am": 234, "hillshade_noon": 238,
        "hillshade_3pm": 135, "horizontal_distance_to_fire_points": 6121,
        "wilderness_area": "Rawah", "soil_type": "C7746",
    },
    {
        "elevation": 3180, "aspect": 155, "slope": 14,
        "horizontal_distance_to_hydrology": 420, "vertical_distance_to_hydrology": 40,
        "horizontal_distance_to_roadways": 2100, "hillshade_9am": 236, "hillshade_noon": 240,
        "hillshade_3pm": 130, "horizontal_distance_to_fire_points": 1500,
        "wilderness_area": "Commanche", "soil_type": "C7756",
    },
    {
        "elevation": 2100, "aspect": 90, "slope": 20,
        "horizontal_distance_to_hydrology": 60, "vertical_distance_to_hydrology": 10,
        "horizontal_distance_to_roadways": 800, "hillshade_9am": 240, "hillshade_noon": 210,
        "hillshade_3pm": 95, "horizontal_distance_to_fire_points": 900,
        "wilderness_area": "Cache", "soil_type": "C4703",
    },
]


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
                response.json()
            except ValueError:
                response.failure("La respuesta no contiene JSON valido")
                return

            response.success()
