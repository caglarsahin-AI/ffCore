# Backend imajı ve geliştirme araçları imajı (tools). Base imajlar REGISTRY_PREFIX ile iç registry'den.
ARG REGISTRY_PREFIX=
FROM ${REGISTRY_PREFIX}ghcr.io/astral-sh/uv:0.10.12 AS uv

FROM ${REGISTRY_PREFIX}python:3.12.10-slim-bookworm AS base
COPY --from=uv /uv /usr/local/bin/uv
# 04a: model weights (bge-m3, reranker, Docling layout, PaddleOCR) live in the model_cache volume
# mounted at /models, never in the image; airgap gets them from the internal mirror (12).
# Offline in every image (review r1 MAJOR-6): only `make models` downloads, on purpose.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models/huggingface \
    MODEL_CACHE_DIR=/models \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1
# 04a (K-04a-0002 S5): libgomp1 is the OpenMP runtime paddlepaddle and the torch CPU build load;
# libgl1, libglib2.0-0 and libxcb1 are what the OpenCV wheels pulled in by PaddleOCR and
# Docling's rapidocr link against (without them `import cv2` fails, and pymupdf4llm with it).
# 12 (FOLLOWUP-95): make and curl (the tools image's) are in this one apt layer, so the tools
# stage has none: with this layer cached, building tools needs no Debian mirror.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libgl1 libglib2.0-0 libxcb1 make curl \
    && rm -rf /var/lib/apt/lists/*
# 12: Python packages from an internal mirror or a wheel directory (deploy/offline/wheels.sh)
# instead of PyPI; uv reads both from the environment. Unset (the default): PyPI.
ARG UV_INDEX_URL
ARG UV_FIND_LINKS
# /models and /data/storage belong to uid 10001 in every image, so the shared volumes are
# writable by backend and worker whichever container mounts them first.
RUN mkdir -p /models /data/storage && chown 10001 /models /data/storage
WORKDIR /app
COPY pyproject.toml uv.lock ./

FROM base AS runtime
RUN uv sync --frozen --no-dev --no-install-project
COPY alembic.ini ./
COPY alembic ./alembic
COPY ffcore ./ffcore
# Home in the model cache: PaddleOCR keeps its weights under ~/.paddleocr.
RUN useradd --system --uid 10001 --home-dir /models ffcore
USER ffcore
EXPOSE 8000
CMD ["uvicorn", "ffcore.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS tools
RUN uv sync --frozen --no-install-project
WORKDIR /work
