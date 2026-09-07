FROM quay.io/jupyter/base-notebook:notebook-7.6.2

# Download and install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install dependencies
COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml
