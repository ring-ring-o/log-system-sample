"""FE/BE で一致が必要なテレメトリ語彙の統合カタログ(SSOT)。

バックエンドを単一源泉とし、フロントが共有すべき値(API ルートのフルパス・共有テレメトリ属性
キー)を構造化して返す。抽出コマンド([interface/cli/telemetry_catalog.py])がこれを
TypeScript へ生成し、FE/BE のパス・属性キーの不一致(タイポ)を構造的に防ぐ。

エラーコードの ``error_catalog`` と同じ「SSOT → 生成 → ``--check``」方式を踏襲する。
"""

from __future__ import annotations

from dataclasses import dataclass

from flownote_api.shared.routes import FRONTEND_ROUTES, FrontendRoute
from flownote_observability.semconv import (
    DEPLOYMENT_ENVIRONMENT_KEY,
    ERROR_TYPE_KEY,
    FLOWNOTE_ERROR_CODE_KEY,
    FLOWNOTE_ERROR_TRACE_ID_KEY,
    HTTP_REQUEST_METHOD_KEY,
    HTTP_RESPONSE_STATUS_CODE_KEY,
    LOG_SCHEMA_VERSION_KEY,
    SERVICE_NAME_KEY,
    SERVICE_VERSION_KEY,
    URL_PATH_KEY,
)


@dataclass(frozen=True, slots=True)
class SharedAttribute:
    """FE/BE が共有するテレメトリ属性/リソースキーの定義。

    Attributes:
        ts_name: TypeScript 側の定数名(``ATTR.<ts_name>``)。
        key: 実際の属性キー文字列(OTel/FlowNote)。
        intent: 用途の説明(生成コメント用)。
    """

    ts_name: str
    key: str
    intent: str


# フロントが共有するルート(フルパス)。``shared.routes`` の SSOT をそのまま用いる。
def shared_routes() -> list[FrontendRoute]:
    """フロントが叩く API ルート(フルパス)を返す。

    Returns:
        名前昇順のフロント共有ルート。
    """
    return sorted(FRONTEND_ROUTES, key=lambda route: route.name)


# FE/BE 双方が出す/参照する属性・リソースキー(共有スキーマを定義する最小集合)。
# BE 内部だけで出すキー(``flownote.task.*``/``gen_ai.*`` 等)は生成共有しない。
_SHARED_ATTRIBUTES: tuple[SharedAttribute, ...] = (
    SharedAttribute("SERVICE_NAME", SERVICE_NAME_KEY, "リソース: サービス名"),
    SharedAttribute("SERVICE_VERSION", SERVICE_VERSION_KEY, "リソース: バージョン"),
    SharedAttribute("DEPLOYMENT_ENVIRONMENT", DEPLOYMENT_ENVIRONMENT_KEY, "リソース: 環境"),
    SharedAttribute("HTTP_REQUEST_METHOD", HTTP_REQUEST_METHOD_KEY, "HTTP メソッド"),
    SharedAttribute("URL_PATH", URL_PATH_KEY, "リクエストパス"),
    SharedAttribute("HTTP_RESPONSE_STATUS_CODE", HTTP_RESPONSE_STATUS_CODE_KEY, "HTTP ステータス"),
    SharedAttribute("ERROR_TYPE", ERROR_TYPE_KEY, "失敗分類(OTel 共通)"),
    SharedAttribute("FLOWNOTE_ERROR_CODE", FLOWNOTE_ERROR_CODE_KEY, "安定エラーコード"),
    SharedAttribute("FLOWNOTE_ERROR_TRACE_ID", FLOWNOTE_ERROR_TRACE_ID_KEY, "エラー相関トレース"),
    SharedAttribute("LOG_SCHEMA_VERSION", LOG_SCHEMA_VERSION_KEY, "ログスキーマ世代"),
)


def shared_attributes() -> list[SharedAttribute]:
    """FE/BE が共有する属性/リソースキーを返す。

    Returns:
        TypeScript 定数名昇順の共有属性。
    """
    return sorted(_SHARED_ATTRIBUTES, key=lambda attr: attr.ts_name)
