"""テレメトリ語彙(semconv/conventions)の契約テスト。

本プロジェクトの基本方針「一意の意図と意味をテストで固定する」に従い、属性キー・列挙値を
ピン留めする。同値だが意図の異なる定数は**別物であること**を明示し、Pydantic alias が
``*_KEY`` 定数と一致することを機械保証する(リテラルの二重管理の事故防止)。
"""

from __future__ import annotations

from flownote_observability import conventions, schema, semconv


def test_resource_keys_are_pinned() -> None:
    # OTel リソース属性キー。ETL/ダッシュボードの契約のため値を固定する。
    assert semconv.SERVICE_NAME_KEY == "service.name"
    assert semconv.SERVICE_VERSION_KEY == "service.version"
    # OTel Stable rename 後の正しいキー(旧 ``deployment.environment`` は使わない)。
    assert semconv.DEPLOYMENT_ENVIRONMENT_KEY == "deployment.environment.name"
    assert semconv.LOG_SCHEMA_VERSION_KEY == "flownote.log.schema_version"


def test_http_and_error_keys_are_pinned() -> None:
    assert semconv.HTTP_REQUEST_METHOD_KEY == "http.request.method"
    assert semconv.HTTP_RESPONSE_STATUS_CODE_KEY == "http.response.status_code"
    assert semconv.HTTP_ROUTE_KEY == "http.route"
    assert semconv.HTTP_SERVER_REQUEST_DURATION_KEY == "http.server.request.duration"
    assert semconv.URL_PATH_KEY == "url.path"
    assert semconv.FLOWNOTE_ERROR_CODE_KEY == "flownote.error.code"
    assert semconv.FLOWNOTE_ERROR_TRACE_ID_KEY == "flownote.error.trace_id"


def test_error_type_and_exception_type_are_distinct() -> None:
    # ``error.type``(低カーディナリティの失敗分類)と ``exception.type``(例外クラス名)は
    # 別意図・別キー。混同するとダッシュボードの分類が壊れるため固定する。
    assert semconv.ERROR_TYPE_KEY == "error.type"
    assert semconv.EXCEPTION_TYPE_KEY == "exception.type"
    assert semconv.ERROR_TYPE_KEY != semconv.EXCEPTION_TYPE_KEY


def test_pydantic_alias_matches_key_constants() -> None:
    # スキーマの alias(mypy/pydantic プラグイン要請でリテラル)が SSOT 定数と一致する。
    fields = schema.LogRecord.model_fields
    assert fields["service_name"].alias == semconv.SERVICE_NAME_KEY
    assert fields["service_version"].alias == semconv.SERVICE_VERSION_KEY
    assert fields["deployment_environment"].alias == semconv.DEPLOYMENT_ENVIRONMENT_KEY
    assert fields["log_schema_version"].alias == semconv.LOG_SCHEMA_VERSION_KEY


def test_event_domain_values_are_pinned() -> None:
    assert conventions.EventDomain.APP == "app"
    assert conventions.EventDomain.ACCESS == "access"
    assert conventions.EventDomain.AUDIT == "audit"
    assert conventions.EventDomain.SECURITY == "security"
    assert conventions.EventDomain.GENAI == "genai"


def test_genai_enum_values_are_pinned() -> None:
    assert conventions.GenAiOperation.CHAT == "chat"
    assert conventions.GenAiOperation.EMBEDDINGS == "embeddings"
    assert conventions.GenAiSystem.STUB == "stub"
    assert conventions.GenAiSystem.OPENAI == "openai"
    assert conventions.GenAiSystem.VLLM == "vllm"
    assert conventions.GenAiTokenType.INPUT == "input"
    assert conventions.GenAiTokenType.OUTPUT == "output"
    assert conventions.GenAiContentKind.PROMPT == "prompt"
    assert conventions.FinishReason.STOP == "stop"


def test_known_namespaces_cover_used_roots() -> None:
    # ``flownote.*`` への寄せ規約で尊重される名前空間ルート。主要な OTel ルートを含む。
    for root in ("http", "gen_ai", "user", "authz", "audit", "error", "exception", "url"):
        assert root in semconv.KNOWN_NAMESPACES
