"""AI モックサーバのテスト。"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from flownote_ai_mock.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """モックサーバへ接続するクライアントを供給する。

    Yields:
        テスト用の非同期 HTTP クライアント。
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


async def test_chat_completion_returns_usage(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/chat/completions",
        json={"model": "qwen", "messages": [{"role": "user", "content": "こんにちは"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["choices"][0]["message"]["content"]
    assert body["usage"]["prompt_tokens"] >= 1


async def test_embeddings_are_deterministic(client: AsyncClient) -> None:
    payload = {"model": "qwen-embed", "input": ["りんご", "みかん"]}
    first = await client.post("/v1/embeddings", json=payload)
    second = await client.post("/v1/embeddings", json=payload)
    assert first.status_code == 200
    # 同一入力は同一ベクトル(再現性)。
    assert first.json()["data"][0]["embedding"] == second.json()["data"][0]["embedding"]
    assert len(first.json()["data"]) == 2
