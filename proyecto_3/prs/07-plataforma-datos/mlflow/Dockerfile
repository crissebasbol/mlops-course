FROM python:3.12-slim

RUN pip install --no-cache-dir mlflow==3.16.1 psycopg2-binary==2.9.11 boto3==1.42.61

COPY start.sh /usr/local/bin/start-mlflow
RUN chmod +x /usr/local/bin/start-mlflow

RUN useradd --create-home --uid 1000 mlflow
USER mlflow
WORKDIR /home/mlflow

EXPOSE 5000
CMD ["start-mlflow"]
