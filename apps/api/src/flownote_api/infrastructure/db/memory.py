"""インメモリのリポジトリ実装。

外部依存なしで動く実装。テスト(ユースケース)と、DB を立てないローカル実行で用いる。
契約テスト([architecture.md] §6)により SQLAlchemy 実装と同じポートを満たすことを保証する。
"""

from __future__ import annotations

from flownote_api.domain.notes import Note
from flownote_api.domain.tasks import Task
from flownote_api.domain.versions import Version


class InMemoryNoteRepository:
    """辞書ベースの :class:`flownote_api.domain.ports.NoteRepository` 実装。"""

    def __init__(self) -> None:
        """空のストアで初期化する。"""
        self._store: dict[str, Note] = {}

    async def add(self, note: Note) -> None:
        """メモを追加する。

        Args:
            note: 追加するメモ。
        """
        self._store[note.id] = note

    async def get(self, note_id: str) -> Note | None:
        """識別子でメモを取得する。

        Args:
            note_id: メモ識別子。

        Returns:
            見つかればメモ、無ければ ``None``。
        """
        return self._store.get(note_id)

    async def list_by_owner(self, owner_id: str) -> list[Note]:
        """所有者のメモを更新日時の降順で返す。

        Args:
            owner_id: 所有ユーザーの不透明ID。

        Returns:
            メモ一覧。
        """
        owned = [n for n in self._store.values() if n.owner_id == owner_id]
        return sorted(owned, key=lambda n: n.updated_at, reverse=True)

    async def update(self, note: Note) -> None:
        """既存メモを更新する。

        Args:
            note: 更新後のメモ。
        """
        self._store[note.id] = note

    async def delete(self, note_id: str) -> None:
        """メモを削除する(存在しなければ無視)。

        Args:
            note_id: メモ識別子。
        """
        self._store.pop(note_id, None)


class InMemoryVersionRepository:
    """辞書ベースの :class:`flownote_api.domain.ports.VersionRepository` 実装。"""

    def __init__(self) -> None:
        """空のストアで初期化する。"""
        self._store: dict[str, Version] = {}

    async def add(self, version: Version) -> None:
        """バージョンを追加する。

        Args:
            version: 追加するバージョン。
        """
        self._store[version.id] = version

    async def list_by_note(self, note_id: str) -> list[Version]:
        """メモのバージョンを生成日時の昇順で返す。

        Args:
            note_id: メモ識別子。

        Returns:
            バージョン一覧。
        """
        owned = [v for v in self._store.values() if v.note_id == note_id]
        return sorted(owned, key=lambda v: v.created_at)

    async def get(self, version_id: str) -> Version | None:
        """識別子でバージョンを取得する。

        Args:
            version_id: バージョン識別子。

        Returns:
            見つかればバージョン、無ければ ``None``。
        """
        return self._store.get(version_id)


class InMemoryTaskRepository:
    """辞書ベースの :class:`flownote_api.domain.ports.TaskRepository` 実装。"""

    def __init__(self) -> None:
        """空のストアで初期化する。"""
        self._store: dict[str, Task] = {}

    async def add(self, task: Task) -> None:
        """タスクを追加する。

        Args:
            task: 追加するタスク。
        """
        self._store[task.id] = task

    async def get(self, task_id: str) -> Task | None:
        """識別子でタスクを取得する。

        Args:
            task_id: タスク識別子。

        Returns:
            見つかればタスク、無ければ ``None``。
        """
        return self._store.get(task_id)

    async def list_by_owner(self, owner_id: str) -> list[Task]:
        """所有者のタスクを更新日時の降順で返す。

        Args:
            owner_id: 所有ユーザーの不透明ID。

        Returns:
            タスク一覧。
        """
        owned = [t for t in self._store.values() if t.owner_id == owner_id]
        return sorted(owned, key=lambda t: t.updated_at, reverse=True)

    async def update(self, task: Task) -> None:
        """既存タスクを更新する。

        Args:
            task: 更新後のタスク。
        """
        self._store[task.id] = task

    async def delete(self, task_id: str) -> None:
        """タスクを削除する(存在しなければ無視)。

        Args:
            task_id: タスク識別子。
        """
        self._store.pop(task_id, None)
