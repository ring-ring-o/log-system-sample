"""バージョン管理(Version)のドメインモデル。

メモの保存ごとに追記専用のバージョンを生成する([architecture.md] §5)。差分計算は
標準ライブラリ ``difflib`` による純粋関数として提供する(外部依存を増やさない)。
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Version:
    """メモのある時点の内容スナップショット(追記専用)。

    Attributes:
        id: バージョン識別子。
        note_id: 対象メモの識別子。
        title: スナップショット時点のタイトル。
        body: スナップショット時点の本文。
        parent_id: 直前バージョンの識別子(初版は ``None``)。
        created_at: 生成時刻(UTC)。
    """

    id: str
    note_id: str
    title: str
    body: str
    parent_id: str | None
    created_at: datetime


def compute_unified_diff(old_body: str, new_body: str, *, context: int = 3) -> str:
    """2つの本文の unified diff を生成する純粋関数。

    Args:
        old_body: 旧本文。
        new_body: 新本文。
        context: 前後に表示する文脈行数。

    Returns:
        unified diff 形式の文字列。差分が無ければ空文字。
    """
    diff_lines = difflib.unified_diff(
        old_body.splitlines(keepends=True),
        new_body.splitlines(keepends=True),
        fromfile="old",
        tofile="new",
        n=context,
    )
    return "".join(diff_lines)
