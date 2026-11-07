FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# تثبيت الأدوات الأساسية التي تتوفر في Ubuntu
RUN apt-get update && apt-get install -y \
    curl git jq python3 python3-pip clang llvm nmap golang-go ca-certificates

# تثبيت أدوات ProjectDiscovery
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest && \
    go install -v github.com/projectdiscovery/ffuf@latest

# تثبيت أدوات بايثون
RUN pip3 install semgrep requests

# تثبيت Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

ENV PATH=$PATH:/root/go/bin
WORKDIR /app
