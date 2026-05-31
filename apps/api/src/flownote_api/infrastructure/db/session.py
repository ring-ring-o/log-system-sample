"""非同期 DB セッションの生成とスキーマ初期化。

ローカル/テストは ``sqlite+aiosqlite``、compose は ``postgresql+psycopg`` を URL で切り替える
([ADR 0003])。本番はマイグレーション(Alembic)を用い、ローカルは簡便のため create_all を使う。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from flownote_api.infrastructure.db.models import Base


def create_engine(database_url: str) -> AsyncEngine:
    """非同期エンジンを生成する。

    Args:
        database_url: SQLAlchemy 接続URL。

    Returns:
        生成された非同期エンジン。
    """
    return create_async_engine(database_url, future=True)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """セッションファクトリを生成する。

    Args:
        engine: 非同期エンジン。

    Returns:
        セッションファクトリ(``expire_on_commit=False``)。
    """
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_models(engine: AsyncEngine) -> None:
    """ORM のスキーマを作成する(ローカル/テスト用)。

    Args:
        engine: 非同期エンジン。
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
