FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Cache heavy dependencies
FROM base AS dependencies
WORKDIR /tmp/deps
RUN pip install --upgrade pip

# Install cpu-only version of torch (required before other dependencies)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch torchvision torchaudio --index-url="https://download.pytorch.org/whl/cpu"

# Application layer - install from wheel
FROM dependencies AS application
WORKDIR /app
RUN mkdir -p ./instance/logs

ARG WHEEL_FILE
COPY ${WHEEL_FILE} /tmp/
RUN pip install /tmp/*.whl[app] && rm /tmp/*.whl
EXPOSE 8888
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8888/v1/health || exit 1

CMD ["sh", "-c", "mkdir -p ./instance/logs && gunicorn --bind 0.0.0.0:8888 --worker-class sync --workers 1 --threads 2 --timeout 45 --keep-alive 2 --max-requests 1000 --max-requests-jitter 50 --access-logfile ./instance/logs/access.log --error-logfile ./instance/logs/error.log --log-level info 'btcopilot.app:create_app()'"]