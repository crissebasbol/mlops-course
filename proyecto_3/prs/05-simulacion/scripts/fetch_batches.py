"""Descarga todos los lotes de la API de datos a una carpeta local (para la simulación offline).

Uso:
    docker run --rm --platform linux/amd64 -p 8089:80 cristiandiaz13/mlops-puj:data-api-pf-v2
    uv run python scripts/fetch_batches.py --api-url http://localhost:8089 --out data/batches
"""

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

END_OF_DATA = "Ya se recolectó toda la información minima necesaria"


def get(url: str, timeout: int) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8089")
    parser.add_argument("--group", type=int, default=1)
    parser.add_argument("--day", default="Tuesday")
    parser.add_argument("--out", type=Path, default=Path("data/batches"))
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    query = urllib.parse.urlencode({"group_number": args.group, "day": args.day})
    args.out.mkdir(parents=True, exist_ok=True)
    if args.restart:
        get(f"{args.api_url}/restart_data_generation?{query}", args.timeout)

    while True:
        status, body = get(f"{args.api_url}/data?{query}", args.timeout)
        if status == 400 and body.get("detail") == END_OF_DATA:
            print("Fin de datos")
            break
        if status != 200:
            raise SystemExit(f"Respuesta inesperada {status}: {body}")
        path = args.out / f"batch_{body['batch_number']}.json"
        path.write_text(json.dumps(body))
        print(f"Lote {body['batch_number']}: {len(body['data'])} filas -> {path}")


if __name__ == "__main__":
    main()
