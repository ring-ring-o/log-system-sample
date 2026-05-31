"""アプリ層(ユースケース)のテスト。

ポートをインメモリ実装で差し替え、ユースケースの振る舞いを高速に検証する
([architecture.md] §6)。AI はスタブ実装を用いる。
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from flownote_api.application.usecases.ai import AIService
from flownote_api.application.usecases.notes import NoteService
from flownote_api.application.usecases.tasks import TaskService
from flownote_api.application.usecases.versions import VersionService
from flownote_api.domain.errors import NotFoundError
from flownote_api.domain.tasks import TaskStatus
from flownote_api.infrastructure.ai.stub import StubAIAssistant
from flownote_api.infrastructure.clock import SystemClock
from flownote_api.infrastructure.db.memory import (
    InMemoryNoteRepository,
    InMemoryTaskRepository,
    InMemoryVersionRepository,
)
from flownote_api.infrastructure.ids import UuidGenerator
from flownote_observability import GenAIInstrumentation, ObservabilityConfig


@dataclass(slots=True)
class _Services:
    """テスト対象のユースケース束。"""

    notes: NoteService
    tasks: TaskService
    versions: VersionService
    ai: AIService


def _build_services() -> _Services:
    """インメモリ + スタブで構成したユースケース束を作る。

    Returns:
        テスト用のサービス束。
    """
    note_repo = InMemoryNoteRepository()
    version_repo = InMemoryVersionRepository()
    task_repo = InMemoryTaskRepository()
    clock = SystemClock()
    ids = UuidGenerator()
    genai = GenAIInstrumentation(
        config=ObservabilityConfig(service_name="test", console_export=False)
    )
    return _Services(
        notes=NoteService(notes=note_repo, versions=version_repo, clock=clock, ids=ids),
        tasks=TaskService(tasks=task_repo, clock=clock, ids=ids),
        versions=VersionService(notes=note_repo, versions=version_repo, clock=clock, ids=ids),
        ai=AIService(assistant=StubAIAssistant(genai), notes=note_repo, tasks=task_repo),
    )


async def test_create_note_makes_initial_version() -> None:
    svc = _build_services()
    note = await svc.notes.create(owner_id="u1", title="メモ", body="本文")
    history = await svc.versions.list(owner_id="u1", note_id=note.id)
    assert len(history) == 1
    assert history[0].parent_id is None


async def test_update_note_appends_version_chain() -> None:
    svc = _build_services()
    note = await svc.notes.create(owner_id="u1", title="t", body="v1")
    await svc.notes.update(owner_id="u1", note_id=note.id, title="t", body="v2")
    history = await svc.versions.list(owner_id="u1", note_id=note.id)
    assert len(history) == 2
    # 2版目は初版を親に持つ(履歴の連結)。
    assert history[1].parent_id == history[0].id


async def test_note_ownership_is_enforced() -> None:
    svc = _build_services()
    note = await svc.notes.create(owner_id="owner", title="t", body="b")
    # 別ユーザーからは存在を秘匿し NotFound。
    with pytest.raises(NotFoundError):
        await svc.notes.get(owner_id="intruder", note_id=note.id)


async def test_version_restore_creates_new_version() -> None:
    svc = _build_services()
    note = await svc.notes.create(owner_id="u1", title="t", body="v1")
    await svc.notes.update(owner_id="u1", note_id=note.id, title="t", body="v2")
    history = await svc.versions.list(owner_id="u1", note_id=note.id)
    await svc.versions.restore(owner_id="u1", note_id=note.id, version_id=history[0].id)
    restored_note = await svc.notes.get(owner_id="u1", note_id=note.id)
    # 復元で本文が初版に戻り、履歴は1件増える。
    assert restored_note.body == "v1"
    assert len(await svc.versions.list(owner_id="u1", note_id=note.id)) == 3


async def test_task_lifecycle() -> None:
    svc = _build_services()
    task = await svc.tasks.create(owner_id="u1", title="やること")
    assert task.status is TaskStatus.TODO
    updated = await svc.tasks.change_status(owner_id="u1", task_id=task.id, status=TaskStatus.DONE)
    assert updated.status is TaskStatus.DONE


async def test_ai_unified_search_finds_relevant_note() -> None:
    svc = _build_services()
    await svc.notes.create(owner_id="u1", title="買い物", body="りんご と みかん を買う")
    await svc.notes.create(owner_id="u1", title="会議", body="議事録")
    hits = await svc.ai.search(owner_id="u1", query="りんご")
    assert hits
    assert hits[0].title == "買い物"


async def test_ai_consult_returns_message() -> None:
    svc = _build_services()
    result = await svc.ai.consult(owner_id="u1", question="何から始める?")
    assert result.message
    assert result.model
