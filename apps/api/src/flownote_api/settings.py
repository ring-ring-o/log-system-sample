"""アプリケーション設定。

環境変数(接頭辞 ``FLOWNOTE_``)から構成を読み取る。バックエンド種別(DB/AI/認証)を切り替え、
ローカルは外部依存なし(sqlite + AIスタブ + dev認証)、compose では実サービスを使う。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic_settings import BaseSettings, SettingsConfigDict


class RepoBackend(StrEnum):
    """リポジトリ実装の選択。

    Attributes:
        SQL: SQLAlchemy。
        MEMORY: インメモリ。
    """

    SQL = "sql"
    MEMORY = "memory"


class AiBackend(StrEnum):
    """AI 実装の選択。

    Attributes:
        STUB: 開発用スタブ。
        OPENAI: OpenAI 互換サーバ。
    """

    STUB = "stub"
    OPENAI = "openai"


class AuthMode(StrEnum):
    """認証方式の選択。

    Attributes:
        DEV: 開発用(署名検証なし)。
        OIDC: Keycloak(OIDC)。
    """

    DEV = "dev"
    OIDC = "oidc"


class Settings(BaseSettings):
    """環境変数で構成されるアプリ設定。

    Attributes:
        environment: 実行環境(``local``/``dev``/``staging``/``prod``)。
        service_version: サービスバージョン。
        database_url: SQLAlchemy 接続URL。
        repo_backend: リポジトリ実装(``sql``/``memory``)。
        ai_backend: AI 実装(``stub``/``openai``)。
        ai_base_url: OpenAI 互換サーバのベースURL。
        ai_chat_model: chat モデル名。
        ai_embedding_model: embeddings モデル名。
        ai_api_key: AI API キー(任意)。
        auth_mode: 認証方式(``dev``/``oidc``)。
        oidc_jwks_url: Keycloak の JWKS URL。
        oidc_issuer: 期待する発行者。
        oidc_audience: 期待する対象者。
        cors_origins: 許可するCORSオリジン。
    """

    model_config = SettingsConfigDict(env_prefix="FLOWNOTE_", env_file=".env", extra="ignore")

    environment: str = "local"
    service_version: str = "0.1.0"

    database_url: str = "sqlite+aiosqlite:///./.tmp/flownote.db"
    repo_backend: RepoBackend = RepoBackend.SQL

    ai_backend: AiBackend = AiBackend.STUB
    ai_base_url: str = "http://localhost:8001"
    ai_chat_model: str = "qwen2.5-instruct"
    ai_embedding_model: str = "qwen2.5-embed"
    ai_api_key: str | None = None

    auth_mode: AuthMode = AuthMode.DEV
    oidc_jwks_url: str = ""
    oidc_issuer: str = ""
    oidc_audience: str = "flownote-api"

    cors_origins: list[str] = ["http://localhost:3000"]
