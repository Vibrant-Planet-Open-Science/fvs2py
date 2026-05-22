ARG FVS_TAG=FS2026.1
ARG FVS_IMAGE=ghcr.io/vibrant-planet-open-science/usfs-fvs:${FVS_TAG}

FROM ${FVS_IMAGE} AS fvs-python-base
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

FROM fvs-python-base AS runtime-base
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv"

FROM runtime-base AS fvs2py
WORKDIR /workspaces/fvs2py
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY fvs2py ./fvs2py
COPY pyproject.toml README.md LICENSE ./
RUN uv pip install --no-deps -e .

FROM fvs-python-base AS dev
RUN if id -u ubuntu >/dev/null 2>&1; then \
    usermod -l fvs2py-dev ubuntu \
    && groupmod -n fvs2py-dev ubuntu \
    && usermod -d /home/fvs2py-dev -m fvs2py-dev; \
    fi
WORKDIR /workspaces/fvs2py
