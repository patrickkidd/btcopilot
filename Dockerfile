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

# Install cpu-only version of torch
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch torchvision torchaudio --index-url="https://download.pytorch.org/whl/cpu"
# btcopilot dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    gunicorn \
    redis \
    celery[redis] \
    flask \
    flask-login \
    flask-session \
    flask-cors \
    flask-sqlalchemy \
    flask-migrate \
    flask-mail \
    openai \
    pygments \
    python-dateutil \
    stripe \
    alembic \
    cachetools \
    rich \
    "sip==6.8.6" \
    "pyqt5==5.15.11" \
    "pyqt5-sip==12.15.0" \
    "pyqt5-qt5==5.15.2" \
    sentence_transformers \
    spacy \
    mistralai \
    pymupdf4llm \
    pydantic_ai \
    assemblyai \
    chromadb \
    langchain \
    langchain-chroma \
    langchain-community \
    langchain-huggingface \
    langchain-openai \
    langchain-text-splitters \
    nest_asyncio \
    pypdf

# Application layer - install from wheel
FROM dependencies AS application
WORKDIR /app
RUN mkdir -p ./instance/logs

ARG WHEEL_FILE
COPY ${WHEEL_FILE} /tmp/
RUN pip install /tmp/*.whl && rm /tmp/*.whl
EXPOSE 8888
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8888/v1/health || exit 1

CMD ["sh", "-c", "mkdir -p ./instance/logs && gunicorn --bind 0.0.0.0:8888 --worker-class sync --workers 1 --threads 2 --timeout 45 --keep-alive 2 --max-requests 1000 --max-requests-jitter 50 --access-logfile ./instance/logs/access.log --error-logfile ./instance/logs/error.log --log-level info 'btcopilot.app:create_app()'"]