"""タスク(Task)のドメインモデル。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from flownote_api.domain.errors import ValidationError


class TaskStatus(StrEnum):
    """タスクの状態。

    Attributes:
        TODO: 未着手。
        DOING: 進行中。
        DONE: 完了。
    """

    TODO = "todo"
    DOING = "doing"
    DONE = "done"


@dataclass(frozen=True, slots=True)
class Task:
    """作業タスク。メモから派生できる。

    Attributes:
        id: タスク識別子。
        owner_id: 所有ユーザーの不透明ID。
        title: タイトル。
        status: 現在の状態。
        note_id: 由来メモの識別子(任意)。
        created_at: 作成時刻(UTC)。
        updated_at: 最終更新時刻(UTC)。
    """

    id: str
    owner_id: str
    title: str
    status: TaskStatus
    note_id: str | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        """タイトルの不変条件を検証する。

        Raises:
            ValidationError: タイトルが空の場合。
        """
        if not self.title.strip():
            raise ValidationError("タイトルは空にできません")

    def with_status(self, status: TaskStatus, *, now: datetime) -> Task:
        """状態を変更した新しいタスクを返す。

        Args:
            status: 新しい状態。
            now: 更新時刻(UTC)。

        Returns:
            状態遷移を反映した新しい :class:`Task`。
        """
        return replace(self, status=status, updated_at=now)

    def is_stalled(self, *, now: datetime, threshold_days: int = 7) -> bool:
        """滞留(一定期間 DOING のまま更新なし)しているか判定する。

        AI 進捗レビュー([progress_review])で滞留タスク抽出に用いる純粋ロジック。

        Args:
            now: 現在時刻(UTC)。
            threshold_days: 滞留とみなす日数。

        Returns:
            DOING かつ最終更新から閾値日数を超えていれば ``True``。
        """
        if self.status is not TaskStatus.DOING:
            return False
        return (now - self.updated_at).days >= threshold_days
