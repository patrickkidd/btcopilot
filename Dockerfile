FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    git \
    # PyQt5.QtCore runtime dependency
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/deps
RUN pip install --upgrade pip

# sops opens the encrypted prompts at run time, with the box's own age key
ARG SOPS_VERSION=3.9.4
RUN curl -fsSL -o /usr/local/bin/sops \
    "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.amd64" \
    && chmod +x /usr/local/bin/sops

# Application layer - install from wheel
FROM base AS application
WORKDIR /app
RUN mkdir -p ./instance/logs

# The dependencies are their own layer, keyed on pyproject.toml, so a code
# change rebuilds only the thin wheel layer below (2026-09-22: the image build
# was 3.5 minutes of reinstalling the same packages every commit).
COPY pyproject.toml /tmp/pyproject.toml
RUN python -c "import tomllib; p = tomllib.load(open('/tmp/pyproject.toml', 'rb'))['project']; print('\n'.join(p.get('dependencies', []) + p['optional-dependencies']['app']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt /tmp/pyproject.toml
ARG WHEEL_FILE
COPY ${WHEEL_FILE} /tmp/
RUN pip install --no-deps "/tmp/$(ls /tmp/*.whl | xargs basename)" && rm /tmp/*.whl

# The private prompts ship encrypted; the key comes from the environment
# (SOPS_AGE_KEY_FILE) on the box, never from the image.
COPY private/prompts /app/private/prompts
ENV FD_PRIVATE_PROMPTS=/app/private/prompts
EXPOSE 8888
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8888/health || exit 1

CMD ["sh", "-c", "mkdir -p ./instance/logs && gunicorn --bind 0.0.0.0:8888 --worker-class gthread --workers 1 --threads 8 --timeout 120 --keep-alive 2 --max-requests 1000 --max-requests-jitter 50 --access-logfile ./instance/logs/access.log --error-logfile ./instance/logs/error.log --log-level info 'btcopilot.app:create_app()'"]