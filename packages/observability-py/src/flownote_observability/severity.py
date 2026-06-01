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


# 4xx のうち、攻撃/異常(Unexpected client error)としてセキュリティ的注意を要する状態。
# これらは WARN。残りの 4xx(仕様内の期待される失敗: 404/422 等)は INFO とする。
# 一律 WARN にするとアラート閾値が健全な利用でも上がり、慣れて無視されるため2段階にする
# ([ログ規約] §3)。
_WARN_CLIENT_ERRORS: frozenset[int] = frozenset(
    {
        401,  # Unauthorized(認証失敗)
        403,  # Forbidden(認可拒否)
        407,  # Proxy Authentication Required
        426,  # Upgrade Required
        428,  # Precondition Required
        429,  # Too Many Requests(レート制限)
    }
)


def severity_for_http_status(status_code: int) -> Severity:
    """HTTP ステータスコードから既定の重大度を決める。

    [ログ規約](../../../docs/observability/logging-spec.md) §3 のルールに従う。
    5xx はサーバ失敗のため ERROR。4xx は2段階に分け、認証/認可/レート制限等の
    **異常・攻撃シグナル**は WARN、バリデーション失敗・未存在など**期待される失敗**は INFO。

    Args:
        status_code: HTTP ステータスコード。

    Returns:
        5xx 以上は ERROR、注意すべき 4xx は WARN、その他の 4xx と 2xx/3xx は INFO。
    """
    if status_code >= 500:
        return Severity.ERROR
    if status_code in _WARN_CLIENT_ERRORS:
        return Severity.WARN
    return Severity.INFO
