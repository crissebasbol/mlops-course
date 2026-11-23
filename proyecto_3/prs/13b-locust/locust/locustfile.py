import json
import logging
import os
import random

from locust import HttpUser, between, events, task

SAMPLE_PATH = os.environ.get("REPLAY_SAMPLE_PATH", "/data/holdout_sample.json")
FEATURES = (
    "status",
    "bed",
    "bath",
    "acre_lot",
    "house_size",
    "prev_sold_date",
    "city",
    "state",
    "zip_code",
    "brokered_by",
)
FALLBACK = {
    "status": "for_sale",
    "bed": 3,
    "bath": 2,
    "acre_lot": 0.25,
    "house_size": 1800,
    "prev_sold_date": "2015-06-15",
    "city": "Springfield",
    "state": "Massachusetts",
    "zip_code": "01109",
    "brokered_by": "22611",
}


def load_sample(path: str) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as handle:
            rows = json.load(handle)
    except (OSError, ValueError):
        return []
    return [row for row in rows if row.get("row_hash")]


SAMPLE = load_sample(SAMPLE_PATH)


@events.init.add_listener
def report_sample(**_):
    if SAMPLE:
        logging.info("Muestra de replay: %s filas holdout desde %s", len(SAMPLE), SAMPLE_PATH)
    else:
        logging.warning("Sin muestra de replay en %s: solo se envía el ejemplo fijo", SAMPLE_PATH)


def features(row: dict) -> dict:
    return {name: row.get(name) for name in FEATURES}


def check(response) -> None:
    if response.status_code != 200:
        response.failure(f"HTTP {response.status_code}")


class PredictUser(HttpUser):
    weight = 4
    wait_time = between(0.5, 1.5)

    @task
    def predict(self):
        body = features(random.choice(SAMPLE)) if SAMPLE else FALLBACK
        with self.client.post(
            "/predict",
            json=body,
            headers={"X-Traffic-Source": "locust"},
            name="/predict",
            catch_response=True,
        ) as response:
            check(response)


class ReplayUser(HttpUser):
    weight = 1
    wait_time = between(0.5, 1.5)

    @task
    def replay(self):
        if not SAMPLE:
            return
        row = random.choice(SAMPLE)
        with self.client.post(
            "/predict",
            json=features(row),
            headers={"X-Traffic-Source": "replay", "X-Replay-Row": row["row_hash"]},
            name="/predict (replay)",
            catch_response=True,
        ) as response:
            check(response)
