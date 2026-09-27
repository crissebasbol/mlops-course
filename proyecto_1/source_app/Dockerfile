FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system --no-cache .

# El CSV viaja dentro de la imagen; al arrancar se copia a Postgres si la tabla esta vacia.
COPY covertype.csv /app/data/covertype.csv
ENV CSV_PATH=/app/data/covertype.csv

EXPOSE 80

CMD ["uvicorn", "source_app:app", "--host", "0.0.0.0", "--port", "80"]
