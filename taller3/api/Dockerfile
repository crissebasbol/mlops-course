FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY api/pyproject.toml api/README.md ./
COPY api/src ./src
RUN uv pip install --system .

# Punto de montaje del volumen models-volume.
RUN mkdir -p /models && chown 50000:0 /models && chmod 775 /models
ENV MODELS_DIR=/models

EXPOSE 8989

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8989"]
