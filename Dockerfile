FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# 1. تثبيت الأدوات الأساسية + zstd (مطلوب لـ Ollama) + python3-venv
RUN apt-get update && apt-get install -y \
    curl git jq python3 python3-pip python3-venv \
    clang llvm nmap golang-go ca-certificates zstd \
    && rm -rf /var/lib/apt/lists/*

# 2. تثبيت أدوات ProjectDiscovery (Go)
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest && \
    go install -v github.com/projectdiscovery/ffuf@latest

# 3. تثبيت أدوات Python (مع تجاوز قيود PEP 668)
RUN pip3 install --break-system-packages semgrep requests

# 4. تثبيت Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# 5. إضافة مسارات Go و Ollama
ENV PATH=$PATH:/root/go/bin:/usr/local/bin

WORKDIR /app
