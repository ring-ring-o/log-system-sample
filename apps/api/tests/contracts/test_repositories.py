"""リポジトリ契約テスト。

同じシナリオをインメモリ実装と SQLAlchemy(SQLite)実装の双方で実行し、両者が同一のポート契約を
満たすことを固定する([architecture.md] §6)。これが詳細設計書に代わる「真実の源泉」となる。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from flownote_api.domain.notes import Note
from flownote_api.domain.ports import NoteRepository, TaskRepository, VersionRepository
from flownote_api.domain.tasks import Task, TaskStatus
from flownote_api.domain.versions import Version
from flownote_api.infrastructure.db.memory import (
    InMemoryNoteRepository,
    InMemoryTaskRepository,
    InMemoryVersionRepository,
)
from flownote_api.infrastructure.db.repositories import (
    SqlNoteRepository,
    SqlTaskRepository,
    SqlVersionRepository,
)
from flownote_api.infrastructure.db.session import (
    create_engine,
    init_models,
    make_session_factory,
)

_NOW = datetime(2026, 5, 31, tzinfo=UTC)

type RepoTriple = tuple[NoteRepository, VersionRepository, TaskRepository]


@pytest.fixture(params=["memory", "sql"])
async def repos(request: pytest.FixtureRequest, tmp_path: Path) -> AsyncIterator[RepoTriple]:
    """インメモリ/SQL の両実装でリポジトリ三種を供給する。

    Args:
        request: パラメータ(``memory``/``sql``)を持つフィクスチャ要求。
        tmp_path: SQLite ファイル用の一時ディレクトリ。

    Yields:
        (メモ, バージョン, タスク) のリポジトリ。
    """
    if request.param == "memory":
        yield (
            InMemoryNoteRepository(),
            InMemoryVersionRepository(),
            InMemoryTaskRepository(),
        )
        return
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'contract.db'}")
    await init_models(engine)
    session_factory = make_session_factory(engine)
    yield (
        SqlNoteRepository(session_factory),
        SqlVersionRepository(session_factory),
        SqlTaskRepository(session_factory),
    )
    await engine.dispose()


async def test_note_repository_crud(repos: RepoTriple) -> None:
    note_repo, _, _ = repos
    note = Note(id="n1", owner_id="u1", title="t", body="b", created_at=_NOW, updated_at=_NOW)
    await note_repo.add(note)
    assert (await note_repo.get("n1")) == note
    assert await note_repo.list_by_owner("u1") == [note]
    # 別所有者には見えない。
    assert await note_repo.list_by_owner("other") == []
    await note_repo.update(note.edited(title="t2", body="b2", now=_NOW))
    fetched = await note_repo.get("n1")
    assert fetched is not None
    assert fetched.title == "t2"
    await note_repo.delete("n1")
    assert (await note_repo.get("n1")) is None


async def test_version_repository_append_only(repos: RepoTriple) -> None:
    note_repo, version_repo, _ = repos
    await note_repo.add(
        Note(id="n1", owner_id="u1", title="t", body="b", created_at=_NOW, updated_at=_NOW)
    )
    v1 = Version(id="v1", note_id="n1", title="t", body="b1", parent_id=None, created_at=_NOW)
    v2 = Version(id="v2", note_id="n1", title="t", body="b2", parent_id="v1", created_at=_NOW)
    await version_repo.add(v1)
    await version_repo.add(v2)
    history = await version_repo.list_by_note("n1")
    assert [v.id for v in history] == ["v1", "v2"]
    assert (await version_repo.get("v2")) == v2


async def test_task_repository_crud(repos: RepoTriple) -> None:
    _, _, task_repo = repos
    task = Task(
        id="t1",
        owner_id="u1",
        title="x",
        status=TaskStatus.TODO,
        note_id=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    await task_repo.add(task)
    assert (await task_repo.get("t1")) == task
    await task_repo.update(task.with_status(TaskStatus.DONE, now=_NOW))
    fetched = await task_repo.get("t1")
    assert fetched is not None
    assert fetched.status is TaskStatus.DONE
    await task_repo.delete("t1")
    assert (await task_repo.get("t1")) is None
