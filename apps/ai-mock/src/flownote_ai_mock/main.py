"""OpenAI 互換モックサーバ。

開発時に vLLM(qwen/gemma)の代替として ``/v1/chat/completions`` と ``/v1/embeddings`` を
決定的に応答する。本番では vLLM 等の実サーバへ差し替える([ADR 0001]/[genai-observability])。
usage(トークン数)も返し、バックエンドの GenAI 計装を現実的に動かせるようにする。
"""

from __future__ import annotations

import hashlib

from fastapi import FastAPI
from pydantic import BaseModel

# 埋め込みベクトルの次元数(モック用の小さな値)。
_EMBEDDING_DIM = 16
# おおよそのトークン換算(4文字=1トークン)。
_CHARS_PER_TOKEN = 4

app = FastAPI(title="FlowNote AI Mock", version="0.1.0")


def _estimate_tokens(text: str) -> int:
    """文字列から概算トークン数を求める。

    Args:
        text: 対象文字列。

    Returns:
        概算トークン数(最低1)。
    """
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _deterministic_embedding(text: str) -> list[float]:
    """テキストから決定的な埋め込みベクトルを生成する。

    ハッシュのバイト列を正規化して用いる。意味的ではないが、同一入力で同一ベクトルとなり
    検索の挙動が再現可能になる。

    Args:
        text: 対象テキスト。

    Returns:
        長さ :data:`_EMBEDDING_DIM` の浮動小数ベクトル。
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [digest[i % len(digest)] / 255.0 for i in range(_EMBEDDING_DIM)]


class ChatMessageIn(BaseModel):
    """chat リクエストのメッセージ。"""

    role: str
    content: str


class ChatRequest(BaseModel):
    """chat completions リクエスト。"""

    model: str
    messages: list[ChatMessageIn]


class EmbeddingRequest(BaseModel):
    """embeddings リクエスト。"""

    model: str
    input: list[str]


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest) -> dict[str, object]:
    """chat completions を模擬する。

    Args:
        request: chat リクエスト。

    Returns:
        OpenAI 互換の応答辞書(usage を含む)。
    """
    last_user = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
    answer = f"(mock) ご質問「{last_user[:40]}」について、次の一歩に分解して取り組みましょう。"
    prompt_tokens = sum(_estimate_tokens(m.content) for m in request.messages)
    completion_tokens = _estimate_tokens(answer)
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


@app.post("/v1/embeddings")
async def embeddings(request: EmbeddingRequest) -> dict[str, object]:
    """embeddings を模擬する。

    Args:
        request: embeddings リクエスト。

    Returns:
        OpenAI 互換の埋め込み応答辞書(usage を含む)。
    """
    data = [
        {"object": "embedding", "index": i, "embedding": _deterministic_embedding(text)}
        for i, text in enumerate(request.input)
    ]
    prompt_tokens = sum(_estimate_tokens(text) for text in request.input)
    return {
        "object": "list",
        "model": request.model,
        "data": data,
        "usage": {"prompt_tokens": prompt_tokens, "total_tokens": prompt_tokens},
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """稼働確認用エンドポイント。

    Returns:
        ステータスを表す辞書。
    """
    return {"status": "ok"}
