# Cloud Cost Prediction API + Model Lab
FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/cloud-cost \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=15 \
    LOG_LEVEL=INFO \
    SPLIT_MODE=temporal \
    SERVING_MODE=primary \
    CANARY_PERCENT=0

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        regina-rexx \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
# Runtime deps first; pytest kept for compose `test` profile without baking ruff.
RUN pip install --no-cache-dir --retries 15 --timeout 120 -r requirements.txt \
    && pip install --no-cache-dir --retries 15 --timeout 120 "pytest==8.4.1"

COPY cloud-cost/ ./cloud-cost/
COPY model_lab/ ./model_lab/
COPY tests/ ./tests/
COPY pytest.ini ./
COPY scripts/ ./scripts/

RUN chmod +x /app/scripts/*.sh

# Train + package at build time; keep a seed copy for empty volume mounts
WORKDIR /app/cloud-cost
RUN python main.py \
    && python -c "from pathlib import Path; assert Path('artifacts/model_bundle/HEAD').is_file()" \
    && mkdir -p /opt/seed \
    && cp -a artifacts /opt/seed/artifacts

WORKDIR /app
RUN python -m model_lab.cli \
    && mkdir -p /opt/seed/model_lab \
    && cp -a model_lab/submission /opt/seed/model_lab/submission \
    && chown -R appuser:appuser /app /opt/seed

EXPOSE 8080 8081

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8080/ready || exit 1

# Entrypoint seeds volumes / fixes ownership as root, then drops to appuser.
WORKDIR /app/cloud-cost
ENTRYPOINT ["/usr/bin/tini", "--", "/app/scripts/entrypoint.sh"]
CMD [ \
  "gunicorn", \
  "--bind", "0.0.0.0:8080", \
  "--workers", "1", \
  "--threads", "8", \
  "--timeout", "60", \
  "--graceful-timeout", "30", \
  "--keep-alive", "5", \
  "--max-requests", "1000", \
  "--max-requests-jitter", "100", \
  "--access-logfile", "-", \
  "--error-logfile", "-", \
  "--capture-output", \
  "app:app" \
]
