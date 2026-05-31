# FlowNote API — マルチステージビルド(軽量ランタイム)。
# builder で uv により依存を解決し、runtime には venv とソースのみを持ち込む。

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app
# ワークスペース解決に必要なファイルを取り込み、flownote-api の依存のみ同期する。
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps/api ./apps/api
COPY apps/ai-mock/pyproject.toml ./apps/ai-mock/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package flownote-api --extra postgres --no-dev --frozen

FROM python:3.14-slim-bookworm AS runtime
# 非rootユーザーで実行。
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/apps/api/src /app/apps/api/src
COPY --from=builder --chown=app:app /app/packages/observability-py/src /app/packages/observability-py/src
ENV PATH="/app/.venv/bin:$PATH" \
    FLOWNOTE_ENV=prod
USER app
EXPOSE 8000
CMD ["uvicorn", "flownote_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
