"""RFC 9457 Problem Details と「境界で1度だけログる」原則の契約テスト。

エラー応答の形式(type/title/status/code/instance/trace_id)、機密の非漏洩、
失敗1件あたりの境界エラーログが1件であることを固定する。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from flownote_api.domain.errors import ConflictError
from flownote_api.main import build_container, create_app
from flownote_api.settings import Settings
from flownote_observability import GenAIInstrumentation, ObservabilityConfig

_EDITOR = {"Authorization": "Bearer alice:editor"}


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """テスト用の例外経路を増設したアプリへ接続するクライアントを供給する。

    Yields:
        テスト用非同期 HTTP クライアント。
    """
    settings = Settings()
    app = create_app(settings)
    app.state.container = build_container(
        settings,
        GenAIInstrumentation(config=ObservabilityConfig(service_name="test", console_export=False)),
    )

    # 競合(409)と未捕捉(500)を意図的に発生させる検証用ルータ。
    probe = APIRouter()

    @probe.get("/_probe/conflict")
    async def _conflict() -> None:
        raise ConflictError(
            "既に存在します", internal_context={"flownote.note.id": "secret-id-xyz"}
        )

    @probe.get("/_probe/boom")
    async def _boom() -> None:
        raise RuntimeError("内部の生メッセージ password=hunter2")

    app.include_router(probe)
    # 意図的に 500 を発生させる検証のため、ASGI 例外を再送出させず応答を観察する。
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


def _logs(text: str) -> list[dict[str, object]]:
    """標準出力から JSON ログ行を抽出する。

    Args:
        text: 捕捉した標準出力。

    Returns:
        パースできた JSON ログの一覧。
    """
    out: list[dict[str, object]] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _attrs(record: dict[str, object]) -> dict[str, object]:
    attrs = record.get("attributes")
    return attrs if isinstance(attrs, dict) else {}


async def test_not_found_returns_rfc9457_problem(client: AsyncClient) -> None:
    response = await client.get("/api/notes/does-not-exist", headers=_EDITOR)
    assert response.status_code == 404
    # RFC 9457 の MIME タイプ。
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"].endswith("RES.NOT_FOUND")
    assert body["code"] == "RES.NOT_FOUND"
    assert body["status"] == 404
    assert body["title"] == "リソースが見つかりません"
    assert body["instance"] == "/api/notes/does-not-exist"
    # trace_id が相関のために載る。
    assert isinstance(body["trace_id"], str) and len(body["trace_id"]) == 32
    # 内部ID(秘匿対象)は応答へ漏れない。
    assert "does-not-exist" not in body.get("detail", "")


async def test_conflict_does_not_leak_internal_context(
    client: AsyncClient, capfd: pytest.CaptureFixture[str]
) -> None:
    capfd.readouterr()
    response = await client.get("/_probe/conflict", headers=_EDITOR)
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "RES.CONFLICT"
    # internal_context(内部ID)は応答に出ない。
    assert "secret-id-xyz" not in json.dumps(body)

    records = _logs(capfd.readouterr().out)
    handled = [r for r in records if _attrs(r).get("flownote.error.code") == "RES.CONFLICT"]
    # 境界ログは1件だけ(log-and-rethrow による重複が無い)。
    assert len(handled) == 1
    # 内部文脈はログ側には出る(応答には出ない)。
    assert _attrs(handled[0]).get("flownote.note.id") == "secret-id-xyz"
    assert handled[0]["severity_text"] == "WARN"


async def test_unhandled_error_is_logged_once_as_error(
    client: AsyncClient, capfd: pytest.CaptureFixture[str]
) -> None:
    capfd.readouterr()
    response = await client.get("/_probe/boom", headers=_EDITOR)
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "GEN.INTERNAL"
    # 生の内部メッセージ(機密含む)は応答に出さない。
    assert "hunter2" not in json.dumps(body)
    assert "password" not in json.dumps(body)

    records = _logs(capfd.readouterr().out)
    errors = [
        r
        for r in records
        if r.get("severity_text") == "ERROR"
        and _attrs(r).get("flownote.error.code") == "GEN.INTERNAL"
    ]
    # ERROR ログは境界で1件だけ。
    assert len(errors) == 1
    # exception.* が付与される。
    assert _attrs(errors[0]).get("exception.type") == "builtins.RuntimeError"
