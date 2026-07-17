FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:/root/.local/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    git \
    libpq-dev \
    postgresql-client \
    python3.12 \
    python3.12-dev \
    python3.12-venv \
 && rm -rf /var/lib/apt/lists/* \
 && ln -sf /usr/bin/python3.12 /usr/local/bin/python \
 && ln -sf /usr/bin/python3.12 /usr/local/bin/python3 \
 && python3.12 -m venv /opt/venv \
 && pip install --upgrade pip

RUN curl https://cursor.com/install -fsS | bash \
 && agent --version

WORKDIR /app

# Bake dependency layers into the image; source code mounts at runtime.
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# Project files come from a host mount at runtime, e.g.:
#   docker run -it -e CURSOR_API_KEY -v "$PWD:/app" <image> bash
