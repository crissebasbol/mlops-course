ARG AIRFLOW_BASE_TAG=3.1.8
FROM apache/airflow:${AIRFLOW_BASE_TAG}

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /requirements.txt

COPY dags/ /opt/airflow/dags/
