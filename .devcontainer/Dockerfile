ARG BASE_IMAGE=daviddanieldiaz/fvs:FS2025.4c
FROM ${BASE_IMAGE}

ARG APP_DIR=/workspaces/fvs2py
ENV APP_DIR=${APP_DIR}
WORKDIR ${APP_DIR}

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt && rm requirements.txt