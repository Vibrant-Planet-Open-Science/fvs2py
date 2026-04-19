ARG BASE_IMAGE=daviddanieldiaz/fvs:FS2025.4c
FROM ${BASE_IMAGE}

ARG APP_DIR=/workspaces/fvs2py
ENV APP_DIR=${APP_DIR}
WORKDIR ${APP_DIR}

COPY requirements.txt requirements-dev.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip freeze > /tmp/constraints.txt \
    && pip install --no-cache-dir -c /tmp/constraints.txt -r requirements-dev.txt \
    && rm requirements.txt requirements-dev.txt /tmp/constraints.txt