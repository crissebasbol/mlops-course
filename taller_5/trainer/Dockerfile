FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN uv pip install --system --no-cache .

CMD ["train"]
