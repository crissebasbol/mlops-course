FROM apache/airflow:2.10.5-python3.12

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

USER airflow

COPY requirements.txt /requirements.txt
RUN uv pip install --no-cache "apache-airflow==${AIRFLOW_VERSION}" -r /requirements.txt
