# المرحلة 1: بناء أدوات Go باستخدام صورة حديثة
FROM golang:1.22-bookworm AS go-builder
# تقليل استهلاك الذاكرة أثناء البناء
ENV GOMAXPROCS=1
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest && \
    go install -v github.com/projectdiscovery/ffuf@latest

# المرحلة 2: الصورة النهائية
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

# تثبيت الأدوات الأساسية
RUN apt-get update && apt-get install -y \
    curl git jq python3 python3-pip python3-venv \
    clang llvm nmap ca-certificates zstd \
    && rm -rf /var/lib/apt/lists/*

# نسخ أدوات Go الجاهزة من مرحلة البناء
COPY --from=go-builder /go/bin/nuclei /usr/local/bin/
COPY --from=go-builder /go/bin/ffuf /usr/local/bin/

# تثبيت أدوات Python
RUN pip3 install --break-system-packages semgrep requests

# تثبيت Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app
