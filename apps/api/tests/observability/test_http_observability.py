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
