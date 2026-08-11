# Build context is the repo root (see render.yaml's dockerContext) because
# backend/app.py imports agents/ and retrieval/ as siblings, not as an
# installed package.
FROM python:3.12-slim

# actionlint is a Go binary, not a Python package (see
# agents/validators/actionlint_validator.py) -- installed via the project's
# official download script, same tool used in Phase 3 development.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://raw.githubusercontent.com/rhysd/actionlint/main/scripts/download-actionlint.bash | bash \
    && mv ./actionlint /usr/local/bin/actionlint \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/ agents/
COPY retrieval/ retrieval/
COPY backend/ backend/
COPY eval/results/ eval/results/
COPY eval/question_set.jsonl eval/question_set.jsonl

# fastembed downloads the bge-small-en-v1.5 ONNX weights (~130MB) into this
# cache on first use; Render's disk is ephemeral per-deploy, so this happens
# once per deploy, not per request.
ENV HF_HOME=/app/.cache/huggingface

EXPOSE 8000
# Render injects $PORT at runtime; shell form so it actually expands.
CMD uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8000}
