FROM python:3.12-slim

ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA} \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    MLFLOW_ENABLE_PROXY_MULTIPART_DOWNLOAD=false \
    MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR=false \
    NUMBA_CACHE_DIR=/tmp/numba

COPY api/requirements.txt /tmp/requirements.txt
COPY housing_ml /tmp/housing_ml
RUN pip install --no-cache-dir -r /tmp/requirements.txt /tmp/housing_ml \
    && rm -rf /tmp/requirements.txt /tmp/housing_ml

RUN useradd --create-home --uid 1000 api
WORKDIR /home/api
COPY --chown=api:api api/housing_api ./housing_api
USER api

RUN python -c "import mlflow.sklearn, shap, skops; from housing_api.main import create_app; create_app()"

EXPOSE 8000
CMD ["uvicorn", "housing_api.main:create_app", "--factory", "--host", "0.0.0.0", \
     "--port", "8000", "--workers", "1", "--no-access-log"]
