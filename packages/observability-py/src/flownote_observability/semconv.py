"""テレメトリ属性キーの単一源泉(SSOT)。

OpenTelemetry セマンティック規約および FlowNote 固有の **共有**属性キーを、意図ごとに
名前付き定数へ集約する。ログ/トレース/メトリクスのキーを文字列リテラルで各所に散らさず、
本モジュール経由で参照することで綴りの一意性(=規約契約)をコード上で担保する
([ログ規約](../../../docs/observability/logging-spec.md) §2,§4)。

線引き:
    - 本モジュールは「OTel 標準キー」と「FE/BE が共有しうる ``flownote.*`` キー」を持つ。
    - アプリ固有のキー(``flownote.note.id`` など)・操作名/イベント名は各アプリ側
      (``apps/api`` の ``shared`` 等)へ置く。
    - 列挙(閉じた値域)の **値** は :mod:`flownote_observability.conventions` に置く。

注意(意図の区別):
    - ``ERROR_TYPE_KEY`` (``error.type``, OTel 失敗分類) と
      ``EXCEPTION_TYPE_KEY`` (``exception.type``, 例外クラス名) は別意図・別キー。
    - サーバ側計測 ``HTTP_SERVER_REQUEST_DURATION_KEY`` と
      クライアント側計測(FE の ``http.client.request.duration``)は別概念。後者は FE 側に置く。
"""

from __future__ import annotations

# --- リソース属性(OTel: ログ/トレースの発生元を表す。スキーマのトップレベルに出る) ---
SERVICE_NAME_KEY = "service.name"
SERVICE_VERSION_KEY = "service.version"
# OTel Stable 化で ``deployment.environment`` は ``deployment.environment.name`` に rename された。
DEPLOYMENT_ENVIRONMENT_KEY = "deployment.environment.name"

# --- ログスキーマのメタ(規約進化時に ETL/パース側が世代判別に使う) ---
LOG_SCHEMA_VERSION_KEY = "flownote.log.schema_version"

# --- イベント分類(業務/アクセス/監査/セキュリティ/GenAI の判別軸) ---
# 値は :class:`flownote_observability.conventions.EventDomain` を用いる。
EVENT_DOMAIN_KEY = "event.domain"

# --- HTTP(OTel セマンティック規約) ---
HTTP_REQUEST_METHOD_KEY = "http.request.method"
HTTP_RESPONSE_STATUS_CODE_KEY = "http.response.status_code"
HTTP_ROUTE_KEY = "http.route"
# サーバ側のリクエスト処理時間(秒, UCUM ``s``)。クライアント計測とは別概念。
HTTP_SERVER_REQUEST_DURATION_KEY = "http.server.request.duration"

# --- URL / ネットワーク / クライアント(OTel) ---
URL_PATH_KEY = "url.path"
CLIENT_ADDRESS_KEY = "client.address"

# --- エラー / 例外(OTel) ---
# 失敗の低カーディナリティ分類(``none`` か例外型名 / fetch 失敗種別)。
ERROR_TYPE_KEY = "error.type"
# ``error.type`` の「失敗なし(成功)」を表す番兵値。
ERROR_TYPE_NONE = "none"
# 例外クラス名・メッセージ・スタックトレース(境界のエラーログで用いる詳細)。
EXCEPTION_TYPE_KEY = "exception.type"
EXCEPTION_MESSAGE_KEY = "exception.message"
EXCEPTION_STACKTRACE_KEY = "exception.stacktrace"
# 安定エラーコード/相関トレース(FE/BE 双方が公開エラーに付与する共有キー)。
FLOWNOTE_ERROR_CODE_KEY = "flownote.error.code"
FLOWNOTE_ERROR_TRACE_ID_KEY = "flownote.error.trace_id"

# --- 認証認可 / 監査(OTel ``user.*`` + FlowNote 監査規約) ---
USER_ID_KEY = "user.id"
USER_ROLES_KEY = "user.roles"
AUTHZ_PERMISSION_KEY = "authz.permission"
AUTHZ_RESOURCE_KEY = "authz.resource"
AUTHZ_DECISION_KEY = "authz.decision"
AUDIT_ACTION_KEY = "audit.action"
AUDIT_OUTCOME_KEY = "audit.outcome"
SECURITY_REASON_KEY = "security.reason"

# --- GenAI(OTel ``gen_ai.*`` セマンティック規約) ---
GEN_AI_OPERATION_NAME_KEY = "gen_ai.operation.name"
GEN_AI_SYSTEM_KEY = "gen_ai.system"
GEN_AI_REQUEST_MODEL_KEY = "gen_ai.request.model"
GEN_AI_REQUEST_TEMPERATURE_KEY = "gen_ai.request.temperature"
GEN_AI_REQUEST_MAX_TOKENS_KEY = "gen_ai.request.max_tokens"
GEN_AI_RESPONSE_MODEL_KEY = "gen_ai.response.model"
GEN_AI_RESPONSE_FINISH_REASONS_KEY = "gen_ai.response.finish_reasons"
GEN_AI_USAGE_INPUT_TOKENS_KEY = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS_KEY = "gen_ai.usage.output_tokens"
GEN_AI_TOKEN_TYPE_KEY = "gen_ai.token.type"

# --- GenAI メトリクス名(計器の識別子) ---
GEN_AI_TOKEN_USAGE_METRIC = "gen_ai.client.token.usage"
GEN_AI_OPERATION_DURATION_METRIC = "gen_ai.client.operation.duration"
FLOWNOTE_AI_COST_METRIC = "flownote.ai.cost.estimate"
FLOWNOTE_AI_REQUEST_COUNT_METRIC = "flownote.ai.request.count"

# --- GenAI 業務属性(FlowNote 固有・AI 計装が共通で付与) ---
FLOWNOTE_AI_USE_CASE_KEY = "flownote.ai.use_case"

# 既知の(=既に名前空間が付いている)属性ルート。これらで始まるキーは ``flownote.*`` に
# 寄せず尊重する(規約 §4.2 のカーディナリティ/衝突回避)。
KNOWN_NAMESPACES: frozenset[str] = frozenset(
    {
        "flownote",
        "http",
        "db",
        "gen_ai",
        "exception",
        "code",
        "user",
        "service",
        "deployment",
        "event",
        "network",
        "client",
        "server",
        "url",
        "error",
        "audit",
        "authz",
        "security",
        "session",
        "rpc",
        "messaging",
        "mcp",
    }
)
