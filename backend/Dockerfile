# Backend imajı ve geliştirme araçları imajı (tools). Base imajlar REGISTRY_PREFIX ile iç registry'den.
ARG REGISTRY_PREFIX=
FROM ${REGISTRY_PREFIX}ghcr.io/astral-sh/uv:0.10.12 AS uv

FROM ${REGISTRY_PREFIX}python:3.12.10-slim-bookworm AS base
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock ./

FROM base AS runtime
RUN uv sync --frozen --no-dev --no-install-project
COPY alembic.ini ./
COPY alembic ./alembic
COPY ffcore ./ffcore
RUN useradd --system --uid 10001 ffcore
USER ffcore
EXPOSE 8000
CMD ["uvicorn", "ffcore.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends make curl \
    && rm -rf /var/lib/apt/lists/*
RUN uv sync --frozen --no-install-project
WORKDIR /work
