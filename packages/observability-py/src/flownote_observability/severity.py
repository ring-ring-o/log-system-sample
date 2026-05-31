"""ログ重大度(Severity)の定義。

[ログ規約](../../../docs/observability/logging-spec.md) §3 に対応し、
6段階の重大度を OpenTelemetry の SeverityNumber に一対一で対応させる。
"""

from __future__ import annotations

from enum import IntEnum


class Severity(IntEnum):
    """ログ重大度。値は OTel SeverityNumber に一致させる。

    Attributes:
        TRACE: 最も詳細な開発用 (OTel=1)。
        DEBUG: 開発・調査用の詳細 (OTel=5)。
        INFO: 正常な業務イベント (OTel=9)。
        WARN: 異常ではないが注意すべき事象 (OTel=13)。
        ERROR: 処理失敗・未捕捉例外・5xx (OTel=17)。
        FATAL: プロセス継続不能 (OTel=21)。
    """

    TRACE = 1
    DEBUG = 5
    INFO = 9
    WARN = 13
    ERROR = 17
    FATAL = 21

    @property
    def text(self) -> str:
        """重大度ラベル文字列を返す。

        Returns:
            ``"INFO"`` などの大文字ラベル。
        """
        return self.name


# structlog のメソッド名 / 一般的なログレベル名から Severity への対応表。
# ``warning`` と ``warn``、``critical`` と ``fatal`` の揺れを吸収する。
_NAME_TO_SEVERITY: dict[str, Severity] = {
    "trace": Severity.TRACE,
    "debug": Severity.DEBUG,
    "info": Severity.INFO,
    "warn": Severity.WARN,
    "warning": Severity.WARN,
    "error": Severity.ERROR,
    "err": Severity.ERROR,
    "exception": Severity.ERROR,
    "critical": Severity.FATAL,
    "fatal": Severity.FATAL,
}


def severity_from_name(name: str) -> Severity:
    """ログレベル名(大小・揺れを許容)から Severity を解決する。

    Args:
        name: ``"info"`` / ``"WARNING"`` / ``"exception"`` などのレベル名。

    Returns:
        対応する :class:`Severity`。未知の名前は :attr:`Severity.INFO` にフォールバックする。
    """
    return _NAME_TO_SEVERITY.get(name.strip().lower(), Severity.INFO)


def severity_for_http_status(status_code: int) -> Severity:
    """HTTP ステータスコードから既定の重大度を決める。

    [ログ規約](../../../docs/observability/logging-spec.md) §3 のルールに従う。
    4xx はクライアント起因のため WARN、5xx はサーバ失敗のため ERROR とする。

    Args:
        status_code: HTTP ステータスコード。

    Returns:
        2xx/3xx は INFO、4xx は WARN、5xx 以上は ERROR。
    """
    if status_code >= 500:
        return Severity.ERROR
    if status_code >= 400:
        return Severity.WARN
    return Severity.INFO
