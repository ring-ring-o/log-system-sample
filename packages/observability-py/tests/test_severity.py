"""重大度マッピングのテスト([ログ規約] §3 の固定)。"""

from __future__ import annotations

from flownote_observability.severity import (
    Severity,
    severity_for_http_status,
    severity_from_name,
)


def test_severity_numbers_match_otel() -> None:
    assert Severity.TRACE == 1
    assert Severity.DEBUG == 5
    assert Severity.INFO == 9
    assert Severity.WARN == 13
    assert Severity.ERROR == 17
    assert Severity.FATAL == 21


def test_severity_from_name_handles_aliases() -> None:
    assert severity_from_name("warning") is Severity.WARN
    assert severity_from_name("WARN") is Severity.WARN
    assert severity_from_name("exception") is Severity.ERROR
    assert severity_from_name("critical") is Severity.FATAL
    # 未知の名前は INFO にフォールバック。
    assert severity_from_name("nonsense") is Severity.INFO


def test_http_status_mapping() -> None:
    assert severity_for_http_status(200) is Severity.INFO
    assert severity_for_http_status(302) is Severity.INFO
    assert severity_for_http_status(404) is Severity.WARN
    assert severity_for_http_status(401) is Severity.WARN
    assert severity_for_http_status(500) is Severity.ERROR
    assert severity_for_http_status(503) is Severity.ERROR
