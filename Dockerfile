# CLaRa-Remembers-It-All Dockerfile
# Multi-stage build for production deployment

# Stage 1: Base image with Python
FROM python:3.11-slim as base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: CUDA variant
FROM nvidia/cuda:12.1-runtime-ubuntu22.04 as cuda-base

WORKDIR /app

# Install Python and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3.11 /usr/bin/python

# Stage 3: Build stage
FROM base as builder

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ src/

# Install package
RUN pip install --no-cache-dir build && \
    python -m build --wheel && \
    pip install --no-cache-dir dist/*.whl

# Stage 4: Production image (CPU/MPS)
FROM base as production

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/clara-server /usr/local/bin/clara-server

# Create non-root user
RUN useradd -m -u 1000 clara && \
    mkdir -p /home/clara/.cache/clara-server && \
    chown -R clara:clara /home/clara

USER clara
WORKDIR /home/clara

# Environment defaults
ENV CLARA_PORT=8765
ENV CLARA_HOST=0.0.0.0
ENV CLARA_CACHE=/home/clara/.cache/clara-server
ENV CLARA_BACKEND=auto

EXPOSE 8765

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8765/health')" || exit 1

CMD ["clara-server"]

# Stage 5: CUDA production image
FROM cuda-base as production-cuda

# Install Python packages
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir .

# Create non-root user
RUN useradd -m -u 1000 clara && \
    mkdir -p /home/clara/.cache/clara-server && \
    chown -R clara:clara /home/clara

USER clara
WORKDIR /home/clara

# Environment defaults
ENV CLARA_PORT=8765
ENV CLARA_HOST=0.0.0.0
ENV CLARA_CACHE=/home/clara/.cache/clara-server
ENV CLARA_BACKEND=cuda

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8765/health')" || exit 1

CMD ["clara-server"]
