# المرحلة 1: بناء أدوات Go باستخدام صورة حديثة (Go 1.26)
FROM golang:1.26-bookworm AS go-builder
ENV GOMAXPROCS=1
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest && \
    go install -v github.com/projectdiscovery/ffuf@latest

# المرحلة 2: الصورة النهائية
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

# 1. تحديث القوائم أولاً
RUN apt-get update

# 2. تثبيت الأدوات مع إعادة المحاولة
RUN for i in 1 2 3; do \
        apt-get install -y --no-install-recommends \
        curl git jq python3 python3-pip python3-venv \
        clang llvm nmap ca-certificates zstd && break || sleep 15; \
    done \
    && rm -rf /var/lib/apt/lists/*

# 3. نسخ أدوات Go الجاهزة
COPY --from=go-builder /go/bin/nuclei /usr/local/bin/
COPY --from=go-builder /go/bin/ffuf /usr/local/bin/

# 4. تثبيت أدوات Python
RUN pip3 install --break-system-packages semgrep requests

# 5. تثبيت Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app
