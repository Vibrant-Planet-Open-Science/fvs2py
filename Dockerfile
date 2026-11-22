FROM ghcr.io/astral-sh/uv:0.7-python3.12-bookworm-slim
RUN useradd -m -s /bin/bash fvs2py-dev
WORKDIR /workspaces/fvs2py
