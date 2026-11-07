FROM ubuntu:22.04

# تجنب الأسئلة أثناء التثبيت
ENV DEBIAN_FRONTEND=noninteractive

# 1. تثبيت الأدوات الأساسية وأدوات الاختراق
RUN apt-get update && apt-get install -y \
    curl git jq python3 python3-pip clang llvm nmap sqlmap gobuster wfuzz \
    golang-go ca-certificates

# 2. تثبيت أدوات ProjectDiscovery
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest && \
    go install -v github.com/projectdiscovery/ffuf@latest

# 3. تثبيت أدوات Python
RUN pip3 install semgrep requests

# 4. تثبيت Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# إضافة مسار Go إلى PATH
ENV PATH=$PATH:/root/go/bin

WORKDIR /app
