"""HTTP 経路の可観測性テスト([logging-spec]/[audit-logging] のE2E固定)。

標準出力に出る構造化ログ(JSON)を捕捉し、相関・アクセスログ・監査/セキュリティログを検証する。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from flownote_api.main import build_container, create_app
from flownote_api.settings import Settings
from flownote_observability import GenAIInstrumentation, ObservabilityConfig

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
    app.state.container = build_container(
        settings,
        GenAIInstrumentation(config=ObservabilityConfig(service_name="test", console_export=False)),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


def _parse_log_lines(text: str) -> list[dict[str, object]]:
    """標準出力テキストから JSON ログ行を抽出する。

    Args:
        text: 捕捉した標準出力。

    Returns:
        パースできた JSON オブジェクトの一覧。
    """
    records: list[dict[str, object]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return records


def _attributes(record: dict[str, object]) -> dict[str, object]:
    """ログレコードから attributes 辞書を安全に取り出す。

    Args:
        record: ログレコード。

    Returns:
        attributes(無ければ空辞書)。
    """
    attrs = record.get("attributes")
    return attrs if isinstance(attrs, dict) else {}


async def test_access_log_is_correlated(
    client: AsyncClient, capfd: pytest.CaptureFixture[str]
) -> None:
    capfd.readouterr()  # 既存出力をクリア
    response = await client.get("/api/notes", headers=_EDITOR)
    assert response.status_code == 200
    # レスポンスに request_id が付与される。
    assert response.headers.get("x-request-id")

    records = _parse_log_lines(capfd.readouterr().out)
    access = [r for r in records if r.get("body") == "http.request.completed"]
    assert access, "アクセスログが出力されていない"
    last = access[-1]
    attrs = _attributes(last)
    assert attrs["http.response.status_code"] == 200
    assert attrs["http.route"] == "/api/notes"
    # 所要時間は OTel 準拠で秒(UCUM `s`)。`*_ms` キーは使わない。
    assert "http.server.request.duration_ms" not in attrs
    duration = attrs["http.server.request.duration"]
    assert isinstance(duration, int | float)
    assert 0 <= duration < 10  # 秒スケール(ミリ秒なら数十〜数百になる)
    # アクセスログがトレースに相関している(FastAPI 自動計装の span)。
    assert isinstance(last["trace_id"], str)


async def test_authz_denied_is_audited(
    client: AsyncClient, capfd: pytest.CaptureFixture[str]
) -> None:
    capfd.readouterr()
    # editor は削除不可 → 認可拒否が監査記録される。
    response = await client.delete("/api/notes/does-not-exist", headers=_EDITOR)
    assert response.status_code == 403

    records = _parse_log_lines(capfd.readouterr().out)
    denied = [
        r
        for r in records
        if _attributes(r).get("event.domain") == "audit"
        and _attributes(r).get("authz.decision") == "deny"
    ]
    assert denied, "認可拒否の監査ログが無い"
    assert denied[-1]["severity_text"] == "WARN"


async def test_invalid_token_is_security_logged(
    client: AsyncClient, capfd: pytest.CaptureFixture[str]
) -> None:
    capfd.readouterr()
    response = await client.get("/api/notes")  # 認証ヘッダなし
    assert response.status_code == 401

    records = _parse_log_lines(capfd.readouterr().out)
    security = [r for r in records if _attributes(r).get("event.domain") == "security"]
    assert security, "セキュリティログが無い"
    assert _attributes(security[-1]).get("audit.action") == "auth.token.verify"


async def test_access_log_route_is_templated(
    client: AsyncClient, capfd: pytest.CaptureFixture[str]
) -> None:
    # 実IDを含むパスへのアクセスでも http.route はテンプレートになる(カーディナリティ規約)。
    created = await client.post("/api/notes", headers=_EDITOR, json={"title": "t", "body": ""})
    note_id = created.json()["id"]
    capfd.readouterr()
    await client.get(f"/api/notes/{note_id}", headers=_EDITOR)

    records = _parse_log_lines(capfd.readouterr().out)
    access = [r for r in records if r.get("body") == "http.request.completed"]
    assert access
    route = _attributes(access[-1]).get("http.route")
    assert route == "/api/notes/{note_id}"
    # 実ID(高カーディナリティ値)はルートに含まれない。
    assert isinstance(route, str)
    assert note_id not in route


async def test_delete_is_audited(client: AsyncClient, capfd: pytest.CaptureFixture[str]) -> None:
    # 削除(機微操作)は admin で実行し、監査ログ(note.delete)に記録される。
    created = await client.post("/api/notes", headers=_ADMIN, json={"title": "t", "body": ""})
    note_id = created.json()["id"]
    capfd.readouterr()
    response = await client.delete(f"/api/notes/{note_id}", headers=_ADMIN)
    assert response.status_code == 204

    records = _parse_log_lines(capfd.readouterr().out)
    deletes = [r for r in records if r.get("body") == "note.delete"]
    assert deletes, "削除の監査ログが無い"
    assert _attributes(deletes[-1]).get("event.domain") == "audit"
    assert _attributes(deletes[-1]).get("authz.resource") == f"note:{note_id}"
