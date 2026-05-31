"""ポート(契約)定義。

[architecture.md](../../../../docs/architecture.md) §3 の「契約の所在」。アプリ層はこの
Protocol にのみ依存し、具体実装(SQLAlchemy/OpenAI互換/Keycloak 等)はインフラ層が提供する。
依存方向を内向きに保つための境界である。
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from flownote_api.domain.ai import (
    ChatMessage,
    ConsultResult,
    ProgressInsight,
    SearchDocument,
    SearchHit,
)
from flownote_api.domain.notes import Note
from flownote_api.domain.tasks import Task
from flownote_api.domain.versions import Version


class Clock(Protocol):
    """現在時刻を供給するポート(テスト容易性のため抽象化)。"""

    def now(self) -> datetime:
        """現在時刻(UTC)を返す。

        Returns:
            タイムゾーン付き現在時刻。
        """
        ...


class IdGenerator(Protocol):
    """識別子を生成するポート。"""

    def new_id(self) -> str:
        """新しい一意な識別子を返す。

        Returns:
            一意な識別子文字列。
        """
        ...


class NoteRepository(Protocol):
    """メモの永続化ポート。"""

    async def add(self, note: Note) -> None:
        """メモを追加する。

        Args:
            note: 追加するメモ。
        """
        ...

    async def get(self, note_id: str) -> Note | None:
        """識別子でメモを取得する。

        Args:
            note_id: メモ識別子。

        Returns:
            見つかればメモ、無ければ ``None``。
        """
        ...

    async def list_by_owner(self, owner_id: str) -> list[Note]:
        """所有者のメモ一覧を返す。

        Args:
            owner_id: 所有ユーザーの不透明ID。

        Returns:
            更新日時の降順を想定したメモ一覧。
        """
        ...

    async def update(self, note: Note) -> None:
        """既存メモを更新する。

        Args:
            note: 更新後のメモ。
        """
        ...

    async def delete(self, note_id: str) -> None:
        """メモを削除する。

        Args:
            note_id: メモ識別子。
        """
        ...


class VersionRepository(Protocol):
    """メモのバージョン履歴の永続化ポート(追記専用)。"""

    async def add(self, version: Version) -> None:
        """バージョンを追加する。

        Args:
            version: 追加するバージョン。
        """
        ...

    async def list_by_note(self, note_id: str) -> list[Version]:
        """メモのバージョン履歴を返す。

        Args:
            note_id: メモ識別子。

        Returns:
            生成日時の昇順を想定したバージョン一覧。
        """
        ...

    async def get(self, version_id: str) -> Version | None:
        """識別子でバージョンを取得する。

        Args:
            version_id: バージョン識別子。

        Returns:
            見つかればバージョン、無ければ ``None``。
        """
        ...


class TaskRepository(Protocol):
    """タスクの永続化ポート。"""

    async def add(self, task: Task) -> None:
        """タスクを追加する。

        Args:
            task: 追加するタスク。
        """
        ...

    async def get(self, task_id: str) -> Task | None:
        """識別子でタスクを取得する。

        Args:
            task_id: タスク識別子。

        Returns:
            見つかればタスク、無ければ ``None``。
        """
        ...

    async def list_by_owner(self, owner_id: str) -> list[Task]:
        """所有者のタスク一覧を返す。

        Args:
            owner_id: 所有ユーザーの不透明ID。

        Returns:
            タスク一覧。
        """
        ...

    async def update(self, task: Task) -> None:
        """既存タスクを更新する。

        Args:
            task: 更新後のタスク。
        """
        ...

    async def delete(self, task_id: str) -> None:
        """タスクを削除する。

        Args:
            task_id: タスク識別子。
        """
        ...


class AIAssistant(Protocol):
    """生成AI 機能のポート。

    実装は OpenAI 互換クライアント(本番/モック)またはインメモリスタブ。いずれの実装も
    [GenAI可観測性規約](../../../../docs/observability/genai-observability.md) に従って計装する。
    """

    async def consult(self, messages: list[ChatMessage]) -> ConsultResult:
        """文脈付きの相談に応答する。

        Args:
            messages: 会話メッセージ列(system/user/assistant)。

        Returns:
            AI の応答。
        """
        ...

    async def search(self, query: str, documents: list[SearchDocument]) -> list[SearchHit]:
        """ドキュメント群に対する統合検索を行う。

        Args:
            query: 検索クエリ。
            documents: 検索対象(メモ/タスクを正規化したもの)。

        Returns:
            関連度順のヒット一覧。
        """
        ...

    async def review_progress(self, tasks: list[Task]) -> ProgressInsight:
        """タスク群の進捗をレビューし提案する。

        Args:
            tasks: レビュー対象のタスク一覧。

        Returns:
            進捗の洞察。
        """
        ...
