"""メモ(Note)のドメインモデル。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from flownote_api.domain.errors import ValidationError

# タイトルの最大長(ドメインの不変条件)。
_MAX_TITLE_LEN = 200


@dataclass(frozen=True, slots=True)
class Note:
    """Markdown メモ。

    不変(frozen)とし、更新は :meth:`edited` で新しいインスタンスを返す宣言的設計とする。

    Attributes:
        id: メモ識別子。
        owner_id: 所有ユーザーの不透明ID。
        title: タイトル(1..200文字)。
        body: Markdown 本文。
        created_at: 作成時刻(UTC)。
        updated_at: 最終更新時刻(UTC)。
    """

    id: str
    owner_id: str
    title: str
    body: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        """タイトルの不変条件を検証する。

        Raises:
            ValidationError: タイトルが空または上限超過の場合。
        """
        if not self.title.strip():
            raise ValidationError("タイトルは空にできません")
        if len(self.title) > _MAX_TITLE_LEN:
            raise ValidationError(f"タイトルは{_MAX_TITLE_LEN}文字以内にしてください")

    def edited(self, *, title: str, body: str, now: datetime) -> Note:
        """編集後の新しいメモを返す。

        Args:
            title: 新しいタイトル。
            body: 新しい本文。
            now: 更新時刻(UTC)。

        Returns:
            更新を反映した新しい :class:`Note`。
        """
        return replace(self, title=title, body=body, updated_at=now)
