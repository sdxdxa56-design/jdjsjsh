FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake pkg-config \
    clang llvm lld \
    cppcheck \
    curl git jq ca-certificates \
    python3 python3-pip python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install \
      requests \
      huggingface_hub \
      semgrep \
      flawfinder \
      bandit \
      llama-cpp-python

WORKDIR /app
