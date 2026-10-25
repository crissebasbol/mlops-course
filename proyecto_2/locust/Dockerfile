FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /locust

COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml

COPY locustfile.py examples.json ./

EXPOSE 8089

ENTRYPOINT ["locust", "-f", "locustfile.py"]
