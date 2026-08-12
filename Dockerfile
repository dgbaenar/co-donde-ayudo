FROM ghcr.io/astral-sh/uv:0.9.28 AS uv
FROM python:3.14-slim-bookworm

COPY --from=uv /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 app \
    && chown -R app:app /app

USER app

CMD ["uv", "run", "--no-sync", "donde-ayudo"]
