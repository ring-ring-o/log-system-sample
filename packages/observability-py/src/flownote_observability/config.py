"""可観測性の構成値。

環境変数から構成を読み取り、ログ/トレース/メトリクスの初期化に用いる。
[可観測性アーキテクチャ](../../../docs/observability/observability-architecture.md) §5 の
環境変数(``OTEL_EXPORTER_OTLP_ENDPOINT`` / ``FLOWNOTE_OTEL_CONSOLE`` 等)に対応する。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, *, default: bool) -> bool:
    """真偽値の環境変数を解釈する。

    Args:
        name: 環境変数名。
        default: 未設定時の既定値。

    Returns:
        ``"1"``/``"true"``/``"yes"``/``"on"`` を真とみなした結果。
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class ObservabilityConfig:
    """可観測性スタックの構成。

    Attributes:
        service_name: 発生元サービス名 (例: ``flownote-api``)。
        service_version: デプロイ識別用バージョン。
        environment: ``local``/``dev``/``staging``/``prod`` のいずれか。
        otlp_endpoint: OTLP/HTTP 送出先。``None`` なら OTLP を無効化しコンソールのみ。
        console_export: トレース/メトリクスをコンソールにも出すか。
        log_level: 既定ログレベル名 (環境別の既定は :meth:`from_env` 参照)。
        genai_capture_content: AI のプロンプト/補完本文をログ化するか(既定 False)。
        genai_content_max_chars: 本文ログ時のトランケート上限文字数。
        trace_sample_ratio: トレースのサンプリング比 (0.0-1.0)。
    """

    service_name: str
    service_version: str = "0.1.0"
    environment: str = "local"
    otlp_endpoint: str | None = None
    console_export: bool = True
    log_level: str = "DEBUG"
    genai_capture_content: bool = False
    genai_content_max_chars: int = 2048
    trace_sample_ratio: float = 1.0

    @classmethod
    def from_env(cls, service_name: str, *, service_version: str = "0.1.0") -> ObservabilityConfig:
        """環境変数から構成を組み立てる。

        環境別の既定ログレベル・サンプリング比は
        [ログ規約](../../../docs/observability/logging-spec.md) §7,§8 に準拠する。

        Args:
            service_name: 発生元サービス名。
            service_version: デプロイ識別用バージョン。

        Returns:
            環境変数を反映した :class:`ObservabilityConfig`。
        """
        environment = os.environ.get("FLOWNOTE_ENV", "local")
        # 本番/ステージングは INFO、それ以外は DEBUG を既定にする。
        default_level = "INFO" if environment in {"prod", "staging"} else "DEBUG"
        # 環境別の既定サンプリング比。
        default_ratio = {"prod": 0.1, "staging": 0.2}.get(environment, 1.0)
        return cls(
            service_name=service_name,
            service_version=os.environ.get("FLOWNOTE_SERVICE_VERSION", service_version),
            environment=environment,
            otlp_endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
            console_export=_env_bool("FLOWNOTE_OTEL_CONSOLE", default=environment == "local"),
            log_level=os.environ.get("FLOWNOTE_LOG_LEVEL", default_level),
            genai_capture_content=_env_bool("FLOWNOTE_GENAI_CAPTURE_CONTENT", default=False),
            genai_content_max_chars=int(os.environ.get("FLOWNOTE_GENAI_MAX_CHARS", "2048")),
            trace_sample_ratio=float(os.environ.get("FLOWNOTE_TRACE_RATIO", str(default_ratio))),
        )
