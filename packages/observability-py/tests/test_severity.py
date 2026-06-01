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
    # 期待される失敗(未存在/検証失敗)は INFO に下げ、アラート閾値を健全に保つ。
    assert severity_for_http_status(404) is Severity.INFO
    assert severity_for_http_status(422) is Severity.INFO
    assert severity_for_http_status(409) is Severity.INFO
    # 異常/攻撃シグナル(認証/認可/レート制限)は WARN。
    assert severity_for_http_status(401) is Severity.WARN
    assert severity_for_http_status(403) is Severity.WARN
    assert severity_for_http_status(429) is Severity.WARN
    # サーバ失敗は ERROR。
    assert severity_for_http_status(500) is Severity.ERROR
    assert severity_for_http_status(503) is Severity.ERROR
