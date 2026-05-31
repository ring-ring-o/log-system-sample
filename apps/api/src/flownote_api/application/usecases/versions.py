"""バージョン管理のユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from flownote_api.domain.errors import NotFoundError
from flownote_api.domain.ports import (
    Clock,
    IdGenerator,
    NoteRepository,
    VersionRepository,
)
from flownote_api.domain.versions import Version, compute_unified_diff
from flownote_observability import get_logger, get_tracer

_logger = get_logger("flownote_api.usecases.versions")
_tracer = get_tracer("flownote_api.usecases.versions")


@dataclass(slots=True)
class VersionService:
    """メモのバージョン履歴・差分・復元を司るユースケース群。

    Attributes:
        notes: メモ永続化ポート。
        versions: バージョン永続化ポート。
        clock: 時刻供給ポート。
        ids: 識別子生成ポート。
    """

    notes: NoteRepository
    versions: VersionRepository
    clock: Clock
    ids: IdGenerator

    async def _assert_owned_note(self, *, owner_id: str, note_id: str) -> None:
        """メモが要求者の所有であることを確認する。

        Args:
            owner_id: 要求者の不透明ID。
            note_id: メモ識別子。

        Raises:
            NotFoundError: 存在しない、または所有者が異なる場合。
        """
        note = await self.notes.get(note_id)
        if note is None or note.owner_id != owner_id:
            raise NotFoundError("note", note_id)

    async def list(self, *, owner_id: str, note_id: str) -> list[Version]:
        """メモのバージョン履歴を返す。

        Args:
            owner_id: 要求者の不透明ID。
            note_id: メモ識別子。

        Returns:
            生成日時昇順のバージョン一覧。
        """
        await self._assert_owned_note(owner_id=owner_id, note_id=note_id)
        return await self.versions.list_by_note(note_id)

    async def diff(
        self, *, owner_id: str, note_id: str, from_version_id: str, to_version_id: str
    ) -> str:
        """2バージョン間の unified diff を返す。

        Args:
            owner_id: 要求者の不透明ID。
            note_id: メモ識別子。
            from_version_id: 比較元バージョン。
            to_version_id: 比較先バージョン。

        Returns:
            unified diff 文字列。

        Raises:
            NotFoundError: いずれかのバージョンが該当メモに存在しない場合。
        """
        await self._assert_owned_note(owner_id=owner_id, note_id=note_id)
        from_version = await self.versions.get(from_version_id)
        to_version = await self.versions.get(to_version_id)
        for version_id, version in (
            (from_version_id, from_version),
            (to_version_id, to_version),
        ):
            if version is None or version.note_id != note_id:
                raise NotFoundError("version", version_id)
        assert from_version is not None  # 上のループで None を除外済み(型の絞り込み)
        assert to_version is not None
        return compute_unified_diff(from_version.body, to_version.body)

    async def restore(self, *, owner_id: str, note_id: str, version_id: str) -> Version:
        """指定バージョンの内容で新しいバージョンを作り、メモを復元する。

        履歴は追記専用のため、復元も「復元内容を持つ新バージョン」を生成する。

        Args:
            owner_id: 要求者の不透明ID。
            note_id: メモ識別子。
            version_id: 復元元バージョン。

        Returns:
            生成された復元バージョン。

        Raises:
            NotFoundError: メモまたはバージョンが存在しない場合。
        """
        with _tracer.start_as_current_span("usecase.version.restore"):
            note = await self.notes.get(note_id)
            if note is None or note.owner_id != owner_id:
                raise NotFoundError("note", note_id)
            source = await self.versions.get(version_id)
            if source is None or source.note_id != note_id:
                raise NotFoundError("version", version_id)

            now = self.clock.now()
            updated_note = note.edited(title=source.title, body=source.body, now=now)
            await self.notes.update(updated_note)
            history = await self.versions.list_by_note(note_id)
            parent_id = history[-1].id if history else None
            restored = Version(
                id=self.ids.new_id(),
                note_id=note_id,
                title=source.title,
                body=source.body,
                parent_id=parent_id,
                created_at=now,
            )
            await self.versions.add(restored)
            _logger.info(
                "note.version.restored",
                **{"flownote.note.id": note_id, "flownote.version.id": version_id},
            )
            return restored
