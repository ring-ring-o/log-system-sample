"""ログレコードのスキーマ定義。

[ログ規約](../../../docs/observability/logging-spec.md) §2 のスキーマを Pydantic で固定する。
本モデルは「構造化ログが規約に準拠するか」をテストで検証するための唯一の実装である。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# OTel リソース属性のドット区切りキー(トップレベル)。
SERVICE_NAME_KEY = "service.name"
SERVICE_VERSION_KEY = "service.version"
# OTel Stable 化で `deployment.environment` は `deployment.environment.name` に rename された。
DEPLOYMENT_ENVIRONMENT_KEY = "deployment.environment.name"
# ログスキーマのバージョン。規約進化時に ETL/パース側が世代を判別できるよう必須で付与する。
LOG_SCHEMA_VERSION_KEY = "flownote.log.schema_version"
LOG_SCHEMA_VERSION = "1"


class LogRecord(BaseModel):
    """規約準拠の構造化ログ1件。

    Pydantic の別名(alias)で OTel のドット区切りキー(``service.name`` 等)を表現する。
    ``populate_by_name=True`` により Python 名でも別名でも生成できる。

    Attributes:
        timestamp: RFC3339(ナノ秒)・UTC の発生時刻。
        severity_text: 重大度ラベル (``INFO`` 等)。
        severity_number: OTel SeverityNumber。
        body: 低カーディナリティのイベント名/メッセージ。
        log_schema_version: ログスキーマ世代(別名 ``flownote.log.schema_version``)。
        service_name: 発生元サービス(別名 ``service.name``)。
        service_version: バージョン(別名 ``service.version``)。
        deployment_environment: 環境(別名 ``deployment.environment.name``)。
        trace_id: 相関トレースID。span 外なら ``None``。
        span_id: 相関 span ID。
        attributes: 構造化属性。
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    timestamp: str
    severity_text: str
    severity_number: int
    body: str
    log_schema_version: str = Field(alias="flownote.log.schema_version")
    # alias は mypy/pydantic プラグインの要請でリテラル文字列を用いる
    # (値は上の *_KEY 定数と一致させること)。
    service_name: str = Field(alias="service.name")
    service_version: str = Field(alias="service.version")
    deployment_environment: str = Field(alias="deployment.environment.name")
    trace_id: str | None = None
    span_id: str | None = None
    # 属性は任意の JSON 互換値を取りうる異種バッグのため object 型とする
    # (``Any`` は使わない方針。値の健全性はマスキングと出力時の JSON 化で担保)。
    attributes: dict[str, object] = Field(default_factory=dict)


# トップレベルに置かれる予約キー(これら以外は ``attributes`` へ集約される)。
RESERVED_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "timestamp",
        "severity_text",
        "severity_number",
        "body",
        LOG_SCHEMA_VERSION_KEY,
        SERVICE_NAME_KEY,
        SERVICE_VERSION_KEY,
        DEPLOYMENT_ENVIRONMENT_KEY,
        "trace_id",
        "span_id",
        "attributes",
    }
)
