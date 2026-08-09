# Cloud Cost Prediction API + Model Lab
FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/cloud-cost \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        regina-rexx \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

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
    && cp -a model_lab/submission /opt/seed/model_lab/submission

EXPOSE 8080 8081

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8080/health || exit 1

WORKDIR /app/cloud-cost
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "app:app"]
