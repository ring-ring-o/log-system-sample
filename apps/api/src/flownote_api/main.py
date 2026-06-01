"""合成ルート(Composition Root)。

設定に基づき具体実装を選んで注入し、FastAPI アプリを組み立てる([architecture.md] §7)。
可観測性(ログ/トレース/メトリクス)を初期化し、FastAPI/SQLAlchemy/httpx を自動計装する。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy.ext.asyncio import AsyncEngine

from flownote_api.application.usecases.ai import AIService
from flownote_api.application.usecases.notes import NoteService
from flownote_api.application.usecases.tasks import TaskService
from flownote_api.application.usecases.versions import VersionService
from flownote_api.container import Container
from flownote_api.domain.identity import Role
from flownote_api.domain.ports import (
    NoteRepository,
    TaskRepository,
    VersionRepository,
)
from flownote_api.infrastructure.ai.openai_compatible import OpenAICompatibleAssistant
from flownote_api.infrastructure.ai.stub import StubAIAssistant
from flownote_api.infrastructure.clock import SystemClock
from flownote_api.infrastructure.db.memory import (
    InMemoryNoteRepository,
    InMemoryTaskRepository,
    InMemoryVersionRepository,
)
from flownote_api.infrastructure.db.repositories import (
    SqlNoteRepository,
    SqlTaskRepository,
    SqlVersionRepository,
)
from flownote_api.infrastructure.db.session import (
    create_engine,
    init_models,
    make_session_factory,
)
from flownote_api.infrastructure.ids import UuidGenerator
from flownote_api.infrastructure.security.token import (
    DevTokenVerifier,
    KeycloakJwtVerifier,
    TokenVerifier,
)
from flownote_api.interface.http.routers import ai, health, notes, tasks, versions
from flownote_api.interface.middleware.errors import register_exception_handlers
from flownote_api.interface.middleware.observability import ObservabilityMiddleware
from flownote_api.settings import Settings
from flownote_observability import GenAIInstrumentation, ObservabilityConfig, bootstrap, get_logger

_logger = get_logger("flownote_api.main")


def _build_repositories(
    settings: Settings, engine: AsyncEngine | None
) -> tuple[NoteRepository, VersionRepository, TaskRepository]:
    """設定に応じてリポジトリ実装を構築する。

    SQL バックエンドでは呼び出し側(lifespan)が生成・破棄まで管理する単一エンジンを共有する。

    Args:
        settings: アプリ設定。
        engine: SQL バックエンド時に共有する非同期エンジン(memory 時は ``None``)。

    Returns:
        (メモ, バージョン, タスク) のリポジトリ。
    """
    if settings.repo_backend == "memory":
        return (
            InMemoryNoteRepository(),
            InMemoryVersionRepository(),
            InMemoryTaskRepository(),
        )
    if engine is None:
        raise RuntimeError("sql バックエンドにはエンジンが必要です")
    session_factory = make_session_factory(engine)
    return (
        SqlNoteRepository(session_factory),
        SqlVersionRepository(session_factory),
        SqlTaskRepository(session_factory),
    )


def _build_token_verifier(settings: Settings) -> TokenVerifier:
    """設定に応じてトークン検証器を構築する。

    Args:
        settings: アプリ設定。

    Returns:
        ``dev`` なら開発用、``oidc`` なら Keycloak 検証器。
    """
    if settings.auth_mode == "oidc":
        return KeycloakJwtVerifier(
            jwks_url=settings.oidc_jwks_url,
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
        )
    # 開発用: 既定で editor 権限を付与(token に role を明示すると上書き)。
    return DevTokenVerifier(default_roles=frozenset({Role.EDITOR}))


def build_container(
    settings: Settings, genai: GenAIInstrumentation, engine: AsyncEngine | None = None
) -> Container:
    """設定から依存コンテナを構築する。

    Args:
        settings: アプリ設定。
        genai: GenAI 計装ファサード。
        engine: SQL バックエンド時に共有する非同期エンジン(memory 時は不要)。

    Returns:
        各ユースケースを束ねた :class:`Container`。
    """
    notes_repo, versions_repo, tasks_repo = _build_repositories(settings, engine)
    clock = SystemClock()
    ids = UuidGenerator()

    if settings.ai_backend == "openai":
        assistant: StubAIAssistant | OpenAICompatibleAssistant = OpenAICompatibleAssistant(
            genai,
            base_url=settings.ai_base_url,
            chat_model=settings.ai_chat_model,
            embedding_model=settings.ai_embedding_model,
            api_key=settings.ai_api_key,
        )
    else:
        assistant = StubAIAssistant(genai, model=settings.ai_chat_model)

    return Container(
        notes=NoteService(notes=notes_repo, versions=versions_repo, clock=clock, ids=ids),
        tasks=TaskService(tasks=tasks_repo, clock=clock, ids=ids),
        versions=VersionService(notes=notes_repo, versions=versions_repo, clock=clock, ids=ids),
        ai=AIService(assistant=assistant, notes=notes_repo, tasks=tasks_repo),
        token_verifier=_build_token_verifier(settings),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """FastAPI アプリを生成する(本番/ローカル用)。

    可観測性を初期化し、自動計装・ミドルウェア・ルータ・例外ハンドラを登録する。依存コンテナは
    起動時(lifespan)に設定から構築し ``app.state`` に格納する。

    Args:
        settings: アプリ設定(省略時は環境変数から構築)。

    Returns:
        構成済みの FastAPI アプリ。
    """
    resolved = settings or Settings()
    obs_config = ObservabilityConfig.from_env(
        "flownote-api", service_version=resolved.service_version
    )
    bootstrap(obs_config)
    genai = GenAIInstrumentation(config=obs_config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # SQL バックエンド時はエンジンを1本だけ生成し、起動〜終了で共有・破棄する。
        engine: AsyncEngine | None = None
        if resolved.repo_backend == "sql":
            if resolved.database_url.startswith("sqlite") and ":///" in resolved.database_url:
                Path(".tmp").mkdir(exist_ok=True)
            engine = create_engine(resolved.database_url)
            await init_models(engine)
            # SQLAlchemy を計装し db.* 属性付き span を得る(ランタイムと同一エンジン)。
            SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
        app.state.container = build_container(resolved, genai, engine)
        # deployment.environment.name はリソース属性として全ログに自動付与されるため、
        # ここでは重複させず業務固有の構成のみ記録する。
        _logger.info(
            "app.started",
            **{
                "flownote.repo_backend": resolved.repo_backend,
                "flownote.ai_backend": resolved.ai_backend,
                "flownote.auth_mode": resolved.auth_mode,
            },
        )
        try:
            yield
        finally:
            # エンジンのコネクションプールを確実に破棄する(リーク防止)。
            if engine is not None:
                await engine.dispose()

    app = FastAPI(title="FlowNote API", version=resolved.service_version, lifespan=lifespan)
    # ミドルウェアを先に追加し、その後 OTel 計装(より外側)で包む。
    app.add_middleware(ObservabilityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origins,
        # 最小権限: 実際に用いる method/header に限定する。
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["authorization", "content-type", "x-request-id", "traceparent"],
    )
    register_exception_handlers(app)
    for module in (health, notes, tasks, versions, ai):
        app.include_router(module.router)

    # 自動計装(HTTP server span / httpx client span)。
    HTTPXClientInstrumentor().instrument()
    FastAPIInstrumentor.instrument_app(app)
    return app


# uvicorn のエントリポイント(``flownote_api.main:app``)。
app = create_app()
