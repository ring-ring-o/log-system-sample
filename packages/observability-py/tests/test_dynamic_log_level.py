"""動的ログレベル(プロセス再起動なしの閾値変更)の契約テスト。

[ログ規約] §7。``set_log_level`` で実行時閾値を上げ下げでき、閾値未満のレコードが
プロセッサ段で破棄されることを固定する。グローバル状態のため前後で確実に復元する。
"""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping

import pytest
import structlog

from flownote_observability import get_log_level, set_log_level
from flownote_observability.config import ObservabilityConfig
from flownote_observability.logging_setup import build_processors

_CONFIG = ObservabilityConfig(service_name="level-test", console_export=False)


@pytest.fixture(autouse=True)
def _restore_level() -> Iterator[None]:
    """テスト後に実行時閾値を緩い既定へ戻し、他テストへの汚染を防ぐ。

    Yields:
        テスト本体の実行。
    """
    yield
    set_log_level("TRACE")


def _run(method: str, event: dict[str, object]) -> dict[str, object] | None:
    """プロセッサ列に1イベントを流す。途中で破棄されたら ``None`` を返す。

    Args:
        method: 呼び出しメソッド名(重大度の決定に使う)。
        event: 入力イベント。

    Returns:
        整形後の辞書、破棄された場合は ``None``。
    """
    processed: MutableMapping[str, object] = dict(event)
    try:
        for processor in build_processors(_CONFIG):
            processed = processor(None, method, processed)
    except structlog.DropEvent:
        return None
    return dict(processed)


def test_raising_level_drops_lower_severity() -> None:
    set_log_level("ERROR")
    assert get_log_level() == "ERROR"
    # INFO/WARN は破棄され、ERROR は通る。
    assert _run("info", {"event": "note.created"}) is None
    assert _run("warning", {"event": "retry"}) is None
    assert _run("error", {"event": "boom"}) is not None


def test_lowering_level_restores_visibility() -> None:
    set_log_level("ERROR")
    assert _run("info", {"event": "x"}) is None
    # 再起動せず DEBUG へ下げると、再び詳細が見えるようになる。
    set_log_level("DEBUG")
    record = _run("info", {"event": "x"})
    assert record is not None
    assert record["severity_text"] == "INFO"
