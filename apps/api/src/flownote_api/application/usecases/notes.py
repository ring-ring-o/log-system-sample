"""メモのユースケース。

ポート(契約)にのみ依存し、具体実装は知らない([architecture.md] §3)。業務境界の計装は
高レベルファサード :func:`operation`/:func:`log_event` に委ねる(span 開始・属性付与・
業務ログ・失敗時 span=ERROR を1行で規約準拠にする。[可観測性アーキテクチャ] §7)。
"""

from __future__ import annotations

from dataclasses import dataclass

from flownote_api.domain.errors import NotFoundError
from flownote_api.domain.notes import Note
from flownote_api.domain.ports import (
    Clock,
    IdGenerator,
    NoteRepository,
    VersionRepository,
)
from flownote_api.domain.versions import Version
from flownote_observability import log_event, operation


@dataclass(slots=True)
class NoteService:
    """メモの作成・取得・更新・削除を司るユースケース群。

    更新・作成時にはバージョンを追記し、履歴を残す。

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

    async def create(self, *, owner_id: str, title: str, body: str) -> Note:
        """メモを新規作成し、初版バージョンを記録する。

        Args:
            owner_id: 所有ユーザーの不透明ID。
            title: タイトル。
            body: Markdown 本文。

        Returns:
            作成されたメモ。
        """
        now = self.clock.now()
        note = Note(
            id=self.ids.new_id(),
            owner_id=owner_id,
            title=title,
            body=body,
            created_at=now,
            updated_at=now,
        )
        # operation 1つで span + 業務ログ + 失敗時 span=ERROR が規約準拠で揃う。
        with operation("note.create") as op:
            op.set(**{"note.id": note.id})
            await self.notes.add(note)
            version = Version(
                id=self.ids.new_id(),
                note_id=note.id,
                title=title,
                body=body,
                parent_id=None,
                created_at=now,
            )
            await self.versions.add(version)
            op.set(**{"version.id": version.id})
        return note

    async def get(self, *, owner_id: str, note_id: str) -> Note:
        """所有者のメモを取得する。

        Args:
            owner_id: 要求者の不透明ID。
            note_id: メモ識別子。

        Returns:
            該当メモ。

        Raises:
            NotFoundError: 存在しない、または所有者が異なる場合。
        """
        note = await self.notes.get(note_id)
        # 所有者が異なる場合は存在を秘匿し NotFound とする(情報漏洩防止)。
        if note is None or note.owner_id != owner_id:
            raise NotFoundError("note", note_id)
        return note

    async def list(self, *, owner_id: str) -> list[Note]:
        """所有者のメモ一覧を返す。

        Args:
            owner_id: 所有ユーザーの不透明ID。

        Returns:
            メモ一覧。
        """
        return await self.notes.list_by_owner(owner_id)

    async def update(self, *, owner_id: str, note_id: str, title: str, body: str) -> Note:
        """メモを更新し、新しいバージョンを追記する。

        Args:
            owner_id: 要求者の不透明ID。
            note_id: メモ識別子。
            title: 新しいタイトル。
            body: 新しい本文。

        Returns:
            更新後のメモ。

        Raises:
            NotFoundError: 存在しない、または所有者が異なる場合。
        """
        with operation("note.update") as op:
            op.set(**{"note.id": note_id})
            current = await self.get(owner_id=owner_id, note_id=note_id)
            now = self.clock.now()
            updated = current.edited(title=title, body=body, now=now)
            await self.notes.update(updated)
            # 直前バージョンを親として履歴を連結する。
            history = await self.versions.list_by_note(note_id)
            parent_id = history[-1].id if history else None
            version = Version(
                id=self.ids.new_id(),
                note_id=note_id,
                title=title,
                body=body,
                parent_id=parent_id,
                created_at=now,
            )
            await self.versions.add(version)
            op.set(**{"version.id": version.id})
            return updated

    async def delete(self, *, owner_id: str, note_id: str) -> None:
        """メモを削除する。

        Args:
            owner_id: 要求者の不透明ID。
            note_id: メモ識別子。

        Raises:
            NotFoundError: 存在しない、または所有者が異なる場合。
        """
        await self.get(owner_id=owner_id, note_id=note_id)
        await self.notes.delete(note_id)
        # span を張るほどでもない単発イベントは log_event で十分。
        log_event("note.deleted", **{"note.id": note_id})
