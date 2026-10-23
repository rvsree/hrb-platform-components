# hrb_platform_components, as a container image.
#
# Build it from the REPOSITORY ROOT, not from anywhere else:
#
#     docker build -t hrb-platform-components:local .
#
# Two stages, same shape as hrb_api_gateway_service's own Dockerfile - this
# service has no spacy/presidio guardrail either (confirmed by grep - no
# presidio/spacy import anywhere under src/).

# ---------------------------------------------------------------------------
# Stage 1 - build the virtual environment
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# git is needed here only because requirements.txt pins hrb-common-libs via
# a git+https URL, not a published PyPI package.
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2 - the image that actually runs
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8200

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 hrbplatform

COPY --from=builder /opt/venv /opt/venv

# /srv holds src/ so imports written as `from src.platform...` (confirmed
# by reading main.py directly) resolve the same way they do locally.
WORKDIR /srv
COPY --chown=hrbplatform:hrbplatform src ./src

USER hrbplatform

EXPOSE 8200

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:8200/ping || exit 1

CMD ["uvicorn", "src.platform.main:app", "--host", "0.0.0.0", "--port", "8200"]
