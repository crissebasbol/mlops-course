FROM quay.io/jupyter/base-notebook:lab-4.6.4

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml /tmp/pyproject.toml
RUN uv pip install --system --no-cache -r /tmp/pyproject.toml

# El CSV viaja dentro de la imagen; el notebook lo carga a Postgres.
COPY covertype.csv /home/jovyan/data/covertype.csv
ENV CSV_PATH=/home/jovyan/data/covertype.csv
