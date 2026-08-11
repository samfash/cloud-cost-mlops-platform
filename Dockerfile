# Cloud Cost Prediction API (+ optional model_lab bake for local Compose)
FROM python:3.13-slim-bookworm

# Render injects service env vars as Docker build-args with the same names.
ARG RENDER_SLIM_BUILD=0
ARG RF_N_JOBS=-1
ARG RF_N_ESTIMATORS=
ARG SKIP_MODEL_LAB_BUILD=0
ARG INSTALL_PYTEST=1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/cloud-cost \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=15 \
    LOG_LEVEL=INFO \
    SPLIT_MODE=temporal \
    SERVING_MODE=primary \
    CANARY_PERCENT=0 \
    LATENCY_MODEL_ENABLED=1 \
    PREDICT_CACHE_ENABLED=1 \
    ASYNC_JOBS_ENABLED=1 \
    AUDIT_LOG_ENABLED=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    RF_N_JOBS=${RF_N_JOBS} \
    RF_N_ESTIMATORS=${RF_N_ESTIMATORS} \
    RENDER_SLIM_BUILD=${RENDER_SLIM_BUILD}

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
RUN pip install --no-cache-dir --retries 15 --timeout 120 -r requirements.txt \
    && if [ "$INSTALL_PYTEST" = "1" ] && [ "$RENDER_SLIM_BUILD" != "1" ]; then \
         pip install --no-cache-dir --retries 15 --timeout 120 "pytest==8.4.1"; \
       fi

COPY cloud-cost/ ./cloud-cost/
COPY model_lab/ ./model_lab/
COPY tests/ ./tests/
COPY pytest.ini ./
COPY scripts/ ./scripts/

RUN chmod +x /app/scripts/*.sh

# Train + package cost/latency models at build time; seed for empty mounts.
WORKDIR /app/cloud-cost
RUN python main.py \
    && python -c "from pathlib import Path; assert Path('artifacts/model_bundle/HEAD').is_file()" \
    && mkdir -p /opt/seed \
    && cp -a artifacts /opt/seed/artifacts

WORKDIR /app
# model_lab election is not served on Render v1 — skip to save build time/RAM.
RUN if [ "$SKIP_MODEL_LAB_BUILD" = "1" ] || [ "$RENDER_SLIM_BUILD" = "1" ]; then \
      mkdir -p /opt/seed/model_lab/submission \
      && printf '%s\n' '{"skipped":true,"reason":"RENDER_SLIM_BUILD"}' \
           > /opt/seed/model_lab/submission/chosen.json \
      && echo "Skipping model_lab bake (slim/Render build)"; \
    else \
      python -m model_lab.cli \
      && mkdir -p /opt/seed/model_lab \
      && cp -a model_lab/submission /opt/seed/model_lab/submission; \
    fi \
    && chown -R appuser:appuser /app /opt/seed

EXPOSE 8080 8081

# Docker HEALTHCHECK uses CMD (not CMD-SHELL). Render also probes healthCheckPath=/ready.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8080/ready || exit 1

WORKDIR /app/cloud-cost
ENTRYPOINT ["/usr/bin/tini", "--", "/app/scripts/entrypoint.sh"]
CMD ["/app/scripts/start_api.sh"]
