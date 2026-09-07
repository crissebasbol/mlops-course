FROM python:3.12-slim

# uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install dependencies declared in pyproject.toml
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system .

# Directory where the versioned models are mounted (shared_storage/models)
ENV MODELS_DIR=/models

EXPOSE 8989

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8989"]
