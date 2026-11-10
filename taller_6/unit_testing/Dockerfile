FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY pyproject.toml ./
COPY ca-bundle.pem /tmp/ca-bundle.pem
RUN SSL_CERT_FILE=/tmp/ca-bundle.pem uv pip install --system --no-cache -r pyproject.toml --group dev

COPY . .

EXPOSE 8000

CMD ["pytest"]
