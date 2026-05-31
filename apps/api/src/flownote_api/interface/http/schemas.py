"""HTTP 境界の DTO(Pydantic)。

[architecture.md](../../../../../docs/architecture.md) §3。境界の入出力を Pydantic で検証する。
ドメインモデルとは分離し、ルータで相互変換する。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from flownote_api.domain.notes import Note
from flownote_api.domain.tasks import Task, TaskStatus
from flownote_api.domain.versions import Version


class NoteCreate(BaseModel):
    """メモ作成リクエスト。"""

    title: str = Field(min_length=1, max_length=200)
    body: str = ""


class NoteUpdate(BaseModel):
    """メモ更新リクエスト。"""

    title: str = Field(min_length=1, max_length=200)
    body: str = ""


class NoteOut(BaseModel):
    """メモ応答。"""

    id: str
    title: str
    body: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, note: Note) -> NoteOut:
        """ドメインモデルから DTO を生成する。

        Args:
            note: ドメインの :class:`Note`。

        Returns:
            応答 DTO。
        """
        return cls(
            id=note.id,
            title=note.title,
            body=note.body,
            created_at=note.created_at,
            updated_at=note.updated_at,
        )


class TaskCreate(BaseModel):
    """タスク作成リクエスト。"""

    title: str = Field(min_length=1, max_length=200)
    note_id: str | None = None


class TaskStatusUpdate(BaseModel):
    """タスク状態変更リクエスト。"""

    status: TaskStatus


class TaskOut(BaseModel):
    """タスク応答。"""

    id: str
    title: str
    status: TaskStatus
    note_id: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, task: Task) -> TaskOut:
        """ドメインモデルから DTO を生成する。

        Args:
            task: ドメインの :class:`Task`。

        Returns:
            応答 DTO。
        """
        return cls(
            id=task.id,
            title=task.title,
            status=task.status,
            note_id=task.note_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


class VersionOut(BaseModel):
    """バージョン応答。"""

    id: str
    note_id: str
    title: str
    parent_id: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, version: Version) -> VersionOut:
        """ドメインモデルから DTO を生成する。

        Args:
            version: ドメインの :class:`Version`。

        Returns:
            応答 DTO。
        """
        return cls(
            id=version.id,
            note_id=version.note_id,
            title=version.title,
            parent_id=version.parent_id,
            created_at=version.created_at,
        )


class DiffOut(BaseModel):
    """差分応答。"""

    diff: str


class ConsultRequest(BaseModel):
    """AI 相談リクエスト。"""

    question: str = Field(min_length=1)
    note_id: str | None = None


class ConsultOut(BaseModel):
    """AI 相談応答。"""

    message: str
    model: str


class SearchRequest(BaseModel):
    """統合検索リクエスト。"""

    query: str = Field(min_length=1)


class SearchHitOut(BaseModel):
    """統合検索のヒット。"""

    kind: str
    id: str
    title: str
    score: float
    snippet: str


class SearchOut(BaseModel):
    """統合検索応答。"""

    hits: list[SearchHitOut]


class ProgressOut(BaseModel):
    """進捗レビュー応答。"""

    summary: str
    stalled_task_ids: list[str]
    suggestions: list[str]
