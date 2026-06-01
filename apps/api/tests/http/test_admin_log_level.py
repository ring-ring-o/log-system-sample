"""動的ログレベル変更エンドポイントの契約テスト(ADMIN 限定)。

プロセス再起動なしの閾値変更を API で行え、権限が無いと 403 になることを固定する。
グローバル状態のため、各テスト後に閾値を緩い既定へ復元する。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from flownote_api.main import build_container, create_app
from flownote_api.settings import Settings
from flownote_observability import GenAIInstrumentation, ObservabilityConfig, set_log_level

_EDITOR = {"Authorization": "Bearer alice:editor"}
_ADMIN = {"Authorization": "Bearer alice:admin"}


@pytest.fixture(autouse=True)
def _restore_level() -> Iterator[None]:
    """テスト後に閾値を緩い既定へ戻し、他テストのログ表示を汚染しない。

    Yields:
        テスト本体の実行。
    """
    yield
    set_log_level("TRACE")


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """インメモリ構成のアプリへ接続するクライアントを供給する。

    Yields:
        テスト用非同期 HTTP クライアント。
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


async def test_admin_can_change_log_level(client: AsyncClient) -> None:
    response = await client.put("/admin/log-level", headers=_ADMIN, json={"level": "ERROR"})
    assert response.status_code == 200
    assert response.json()["level"] == "ERROR"
    # 反映後は GET でも ERROR が見える。
    current = await client.get("/admin/log-level", headers=_ADMIN)
    assert current.json()["level"] == "ERROR"


async def test_editor_cannot_change_log_level(client: AsyncClient) -> None:
    # 管理権限の無い editor は 403(Problem Details)。
    response = await client.put("/admin/log-level", headers=_EDITOR, json={"level": "DEBUG"})
    assert response.status_code == 403
    assert response.json()["code"] == "AUTHZ.DENIED"
