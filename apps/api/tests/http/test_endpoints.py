"""HTTP エンドポイントの結合テスト。

実アプリ(create_app)をインメモリ構成で起動し、垂直導線(メモ→バージョン→タスク→AI)と
認証認可(401/403)を検証する。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from flownote_api.main import build_container, create_app
from flownote_api.settings import Settings
from flownote_observability import GenAIInstrumentation, ObservabilityConfig

# 開発トークン: ``<sub>:<roles>``。
_EDITOR = {"Authorization": "Bearer alice:editor"}
_ADMIN = {"Authorization": "Bearer alice:admin"}


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """インメモリ構成のアプリに接続する HTTP クライアントを供給する。

    Yields:
        テスト用の非同期 HTTP クライアント。
    """
    settings = Settings()
    app = create_app(settings)
    # lifespan を介さず、テスト用コンテナを直接注入する。
    app.state.container = build_container(
        settings,
        GenAIInstrumentation(config=ObservabilityConfig(service_name="test", console_export=False)),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


async def test_health_requires_no_auth(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_unauthenticated_request_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/notes")
    assert response.status_code == 401


async def test_note_version_task_ai_flow(client: AsyncClient) -> None:
    # メモ作成 → 更新(バージョン追記) → 履歴/差分 → タスク化 → AI検索/相談 の垂直導線。
    created = await client.post(
        "/api/notes", headers=_EDITOR, json={"title": "買い物", "body": "りんごを買う"}
    )
    assert created.status_code == 201
    note_id = created.json()["id"]

    await client.put(
        f"/api/notes/{note_id}",
        headers=_EDITOR,
        json={"title": "買い物", "body": "りんごとみかんを買う"},
    )
    versions = await client.get(f"/api/notes/{note_id}/versions", headers=_EDITOR)
    assert versions.status_code == 200
    version_items = versions.json()
    assert len(version_items) == 2

    diff = await client.get(
        f"/api/notes/{note_id}/versions/diff",
        headers=_EDITOR,
        params={"from_version": version_items[0]["id"], "to_version": version_items[1]["id"]},
    )
    assert "みかん" in diff.json()["diff"]

    task = await client.post(
        "/api/tasks", headers=_EDITOR, json={"title": "買い物に行く", "note_id": note_id}
    )
    assert task.status_code == 201

    search = await client.post("/api/ai/search", headers=_EDITOR, json={"query": "りんご"})
    assert search.status_code == 200
    assert search.json()["hits"]

    consult = await client.post(
        "/api/ai/consult", headers=_EDITOR, json={"question": "何から始める?"}
    )
    assert consult.status_code == 200
    assert consult.json()["message"]


async def test_delete_requires_admin_role(client: AsyncClient) -> None:
    created = await client.post("/api/notes", headers=_EDITOR, json={"title": "t", "body": ""})
    note_id = created.json()["id"]

    # editor は削除権限を持たない → 403。
    denied = await client.delete(f"/api/notes/{note_id}", headers=_EDITOR)
    assert denied.status_code == 403

    # admin は削除可 → 204。
    allowed = await client.delete(f"/api/notes/{note_id}", headers=_ADMIN)
    assert allowed.status_code == 204
