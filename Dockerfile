ARG BASE_IMAGE="ubuntu:latest"
FROM ${BASE_IMAGE} AS builder

USER root

WORKDIR /build
ENV FC=gfortran
ARG FVS_VERSION
RUN apt-get update \
    && apt-get install -y git build-essential gfortran cmake unixodbc-dev
RUN git clone -b "${FVS_VERSION}" --recurse-submodules https://github.com/USDAForestService/ForestVegetationSimulator.git 
RUN cd /build/ForestVegetationSimulator/bin \
    && make US


FROM python:3.11-slim AS runtime
COPY --from=builder /build/ForestVegetationSimulator/bin/FVS??.so /usr/local/lib
COPY --from=builder /build/ForestVegetationSimulator/bin/FVS?? /usr/local/bin

ARG APP_DIR=/workspaces/fvs2py
ENV APP_DIR=${APP_DIR}
WORKDIR ${APP_DIR}

COPY ./requirements.txt .
ENV PIP_PREFER_BINARY=1
RUN pip install --upgrade pip pip-tools \
    && pip install --no-cache-dir --upgrade -r requirements.txt \
    && rm requirements.txt
COPY ./fvs2py ${APP_DIR}/fvs2py