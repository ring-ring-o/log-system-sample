# apps/ai-mock — OpenAI 互換モックサーバ（開発用）

開発時に vLLM（qwen/gemma 等）の代替として **OpenAI 互換 API を決定的に応答する**軽量 FastAPI サーバ。
vLLM は重いため、ローカルでは本サーバで AI 呼び出しを模擬し、バックエンドの GenAI 計装を現実的に動かせるようにする
（[CLAUDE.md §9](../../CLAUDE.md) / [genai-observability.md](../../docs/observability/genai-observability.md)）。

## エンドポイント

| メソッド | パス | 説明 |
|---|---|---|
| POST | `/v1/chat/completions` | chat 応答を模擬。最後の user メッセージを反映した決定的な回答 + `usage`（トークン数）を返す |
| POST | `/v1/embeddings` | 入力ハッシュから決定的な埋め込みベクトル（16 次元）+ `usage` を返す |
| GET | `/health` | 稼働確認 |

- **決定的**: 応答・埋め込みは入力から一意に定まり、検索の挙動が再現可能。意味的な埋め込みではない。
- **usage を返す**: トークン数（おおよそ 4 文字 = 1 トークン）を返し、バックエンドの GenAI 計装（トークン計測）を検証できる。
- 本番では vLLM 等の実サーバへ差し替える（OpenAI 互換のため URL 差し替えのみ）。

## コマンド（リポジトリルートから / Python 3.14・uv）

```bash
uv sync
uv run --package flownote-ai-mock uvicorn flownote_ai_mock.main:app --port 8001   # 起動(:8001)
uv run pytest apps/ai-mock                # テスト
```

Docker: [`Dockerfile`](./Dockerfile)。compose では `ai-mock` サービスとして起動する（[infra/](../../infra/)）。

## バックエンドとの接続

[apps/api](../api/README.md) は `FLOWNOTE_AI_BACKEND=openai` かつ `FLOWNOTE_AI_BASE_URL=http://localhost:8001`
（compose 内では `http://ai-mock:8001`）で本サーバを参照する。既定の `stub` バックエンドはサーバ不要のため、
本サーバは GenAI 計装を HTTP 越しに確認したいときに用いる。

## 実装

単一ファイル [`src/flownote_ai_mock/main.py`](./src/flownote_ai_mock/main.py)。依存は FastAPI / uvicorn / pydantic のみ。
