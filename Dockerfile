ARG FVS_TAG=FS2026.2
ARG FVS_IMAGE=ghcr.io/vibrant-planet-open-science/usfs-fvs:${FVS_TAG}

FROM ${FVS_IMAGE} AS base
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
    python3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

FROM base AS runtime
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /workspaces/fvs2py
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY fvs2py ./fvs2py
COPY README.md LICENSE ./
RUN uv sync --frozen --no-dev

FROM base AS dev
RUN if id -u ubuntu >/dev/null 2>&1; then \
    usermod -l fvs2py-dev ubuntu \
    && groupmod -n fvs2py-dev ubuntu \
    && usermod -d /home/fvs2py-dev -m fvs2py-dev; \
    fi
WORKDIR /workspaces/fvs2py
