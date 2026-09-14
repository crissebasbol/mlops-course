FROM apache/airflow:2.10.5-python3.12

USER root

RUN mkdir -p /opt/airflow/models \
    && chown -R airflow:root /opt/airflow/models \
    && chmod -R 775 /opt/airflow/models

USER airflow

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

COPY --chown=airflow:root data/penguins.csv /opt/airflow/data/penguins.csv
