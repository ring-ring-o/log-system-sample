"""SQLAlchemy(async)によるリポジトリ実装。

ポート([domain.ports])を満たす。ORM 行とドメインモデルを境界で相互変換し、ドメインを永続化技術
から独立に保つ([ADR 0003])。各操作はセッション単位のトランザクションで、SQLAlchemy 計装により
``db.*`` 属性付きの span が生成される。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flownote_api.domain.notes import Note
from flownote_api.domain.tasks import Task, TaskStatus
from flownote_api.domain.versions import Version
from flownote_api.infrastructure.db.models import NoteRow, TaskRow, VersionRow


def _utc(value: datetime) -> datetime:
    """naive な datetime に UTC を付与し、バックエンド差を吸収する。

    SQLite はタイムゾーンを保持しないため naive で返る。ドメインへは常にタイムゾーン付き
    (UTC)で渡し、PostgreSQL(timestamptz)と同一の契約を満たす。

    Args:
        value: DB から得た日時。

    Returns:
        タイムゾーン付き(UTC)の日時。
    """
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _to_note(row: NoteRow) -> Note:
    """ORM 行をメモのドメインモデルへ変換する。

    Args:
        row: メモの永続化行。

    Returns:
        ドメインの :class:`Note`。
    """
    return Note(
        id=row.id,
        owner_id=row.owner_id,
        title=row.title,
        body=row.body,
        created_at=_utc(row.created_at),
        updated_at=_utc(row.updated_at),
    )


def _to_version(row: VersionRow) -> Version:
    """ORM 行をバージョンのドメインモデルへ変換する。

    Args:
        row: バージョンの永続化行。

    Returns:
        ドメインの :class:`Version`。
    """
    return Version(
        id=row.id,
        note_id=row.note_id,
        title=row.title,
        body=row.body,
        parent_id=row.parent_id,
        created_at=_utc(row.created_at),
    )


def _to_task(row: TaskRow) -> Task:
    """ORM 行をタスクのドメインモデルへ変換する。

    Args:
        row: タスクの永続化行。

    Returns:
        ドメインの :class:`Task`。
    """
    return Task(
        id=row.id,
        owner_id=row.owner_id,
        title=row.title,
        status=TaskStatus(row.status),
        note_id=row.note_id,
        created_at=_utc(row.created_at),
        updated_at=_utc(row.updated_at),
    )


class SqlNoteRepository:
    """SQLAlchemy によるメモリポジトリ。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """セッションファクトリで初期化する。

        Args:
            session_factory: 非同期セッションファクトリ。
        """
        self._sf = session_factory

    async def add(self, note: Note) -> None:
        """メモを追加する。

        Args:
            note: 追加するメモ。
        """
        async with self._sf() as session:
            session.add(
                NoteRow(
                    id=note.id,
                    owner_id=note.owner_id,
                    title=note.title,
                    body=note.body,
                    created_at=note.created_at,
                    updated_at=note.updated_at,
                )
            )
            await session.commit()

    async def get(self, note_id: str) -> Note | None:
        """識別子でメモを取得する。

        Args:
            note_id: メモ識別子。

        Returns:
            見つかればメモ、無ければ ``None``。
        """
        async with self._sf() as session:
            row = await session.get(NoteRow, note_id)
            return _to_note(row) if row is not None else None

    async def list_by_owner(self, owner_id: str) -> list[Note]:
        """所有者のメモを更新日時の降順で返す。

        Args:
            owner_id: 所有ユーザーの不透明ID。

        Returns:
            メモ一覧。
        """
        async with self._sf() as session:
            stmt = (
                select(NoteRow)
                .where(NoteRow.owner_id == owner_id)
                .order_by(NoteRow.updated_at.desc())
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_to_note(row) for row in rows]

    async def update(self, note: Note) -> None:
        """既存メモを更新する。

        Args:
            note: 更新後のメモ。
        """
        async with self._sf() as session:
            row = await session.get(NoteRow, note.id)
            if row is None:
                return
            row.title = note.title
            row.body = note.body
            row.updated_at = note.updated_at
            await session.commit()

    async def delete(self, note_id: str) -> None:
        """メモを削除する。

        Args:
            note_id: メモ識別子。
        """
        async with self._sf() as session:
            await session.execute(delete(NoteRow).where(NoteRow.id == note_id))
            await session.commit()


class SqlVersionRepository:
    """SQLAlchemy によるバージョンリポジトリ。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """セッションファクトリで初期化する。

        Args:
            session_factory: 非同期セッションファクトリ。
        """
        self._sf = session_factory

    async def add(self, version: Version) -> None:
        """バージョンを追加する。

        Args:
            version: 追加するバージョン。
        """
        async with self._sf() as session:
            session.add(
                VersionRow(
                    id=version.id,
                    note_id=version.note_id,
                    title=version.title,
                    body=version.body,
                    parent_id=version.parent_id,
                    created_at=version.created_at,
                )
            )
            await session.commit()

    async def list_by_note(self, note_id: str) -> list[Version]:
        """メモのバージョンを生成日時の昇順で返す。

        Args:
            note_id: メモ識別子。

        Returns:
            バージョン一覧。
        """
        async with self._sf() as session:
            stmt = (
                select(VersionRow)
                .where(VersionRow.note_id == note_id)
                .order_by(VersionRow.created_at.asc())
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_to_version(row) for row in rows]

    async def get(self, version_id: str) -> Version | None:
        """識別子でバージョンを取得する。

        Args:
            version_id: バージョン識別子。

        Returns:
            見つかればバージョン、無ければ ``None``。
        """
        async with self._sf() as session:
            row = await session.get(VersionRow, version_id)
            return _to_version(row) if row is not None else None


class SqlTaskRepository:
    """SQLAlchemy によるタスクリポジトリ。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """セッションファクトリで初期化する。

        Args:
            session_factory: 非同期セッションファクトリ。
        """
        self._sf = session_factory

    async def add(self, task: Task) -> None:
        """タスクを追加する。

        Args:
            task: 追加するタスク。
        """
        async with self._sf() as session:
            session.add(
                TaskRow(
                    id=task.id,
                    owner_id=task.owner_id,
                    title=task.title,
                    status=task.status.value,
                    note_id=task.note_id,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                )
            )
            await session.commit()

    async def get(self, task_id: str) -> Task | None:
        """識別子でタスクを取得する。

        Args:
            task_id: タスク識別子。

        Returns:
            見つかればタスク、無ければ ``None``。
        """
        async with self._sf() as session:
            row = await session.get(TaskRow, task_id)
            return _to_task(row) if row is not None else None

    async def list_by_owner(self, owner_id: str) -> list[Task]:
        """所有者のタスクを更新日時の降順で返す。

        Args:
            owner_id: 所有ユーザーの不透明ID。

        Returns:
            タスク一覧。
        """
        async with self._sf() as session:
            stmt = (
                select(TaskRow)
                .where(TaskRow.owner_id == owner_id)
                .order_by(TaskRow.updated_at.desc())
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_to_task(row) for row in rows]

    async def update(self, task: Task) -> None:
        """既存タスクを更新する。

        Args:
            task: 更新後のタスク。
        """
        async with self._sf() as session:
            row = await session.get(TaskRow, task.id)
            if row is None:
                return
            row.title = task.title
            row.status = task.status.value
            row.note_id = task.note_id
            row.updated_at = task.updated_at
            await session.commit()

    async def delete(self, task_id: str) -> None:
        """タスクを削除する。

        Args:
            task_id: タスク識別子。
        """
        async with self._sf() as session:
            await session.execute(delete(TaskRow).where(TaskRow.id == task_id))
            await session.commit()
