# apps/api — FlowNote バックエンド (FastAPI)

FlowNote のバックエンド API。メモ／タスク／バージョン管理／AI 支援を提供する FastAPI アプリで、
**レイヤードアーキテクチャ**（`domain` / `application` / `infrastructure` / `interface`）と
**可観測性の中核計装**（OTel トレース・構造化ログ・メトリクス・GenAI 計装）を備える。

> このアプリは題材であり、真の成果物は可観測性システムである。実装判断は
> [ログ規約(SSOT)](../../docs/observability/logging-spec.md) と
> [可観測性アーキテクチャ](../../docs/observability/observability-architecture.md) を優先する。

## アーキテクチャ（一方向依存）

```
interface  ─→ application ─→ domain          interface(http/middleware/security)
infrastructure ─→ application / domain        application(usecases)
                                              domain(モデル/ポート/エラー・外向き依存ゼロ)
                                              infrastructure(db/ai/security/clock/ids)
```

- **domain**: 純粋な dataclass / 値オブジェクト・ポート（Protocol）。フレームワーク非依存。
- **application**: ユースケース（`notes` / `tasks` / `versions` / `ai`）。
- **infrastructure**: ポートの具体実装（SQLAlchemy リポジトリ・OpenAI互換/スタブ AI・JWT 検証・時計・ID）。
- **interface**: HTTP ルータ・スキーマ（Pydantic）・ミドルウェア（可観測性/例外）・認証。
- 合成ルートは [`main.py`](./src/flownote_api/main.py)、依存コンテナは [`container.py`](./src/flownote_api/container.py)。
  詳細は [docs/architecture.md](../../docs/architecture.md) §7。

## エンドポイント

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/health` | 稼働確認（認証不要） |
| POST/GET/GET/PUT/DELETE | `/api/notes`（`/{note_id}`） | メモの CRUD |
| GET/GET/POST | `/api/notes/{note_id}/versions`（`/diff`, `/{version_id}/restore`） | バージョン一覧・差分・復元 |
| POST/GET/PATCH/DELETE | `/api/tasks`（`/{task_id}/status`） | タスク CRUD・状態更新 |
| POST/POST/GET | `/api/ai/consult`, `/api/ai/search`, `/api/ai/progress` | AI 相談・検索・進捗 |
| GET/PUT | `/admin/log-level` | 動的ログレベル参照・変更（`ADMIN` 限定・再起動不要） |

## 設定（環境変数 `FLOWNOTE_` 接頭辞）

[`settings.py`](./src/flownote_api/settings.py) 参照。バックエンド種別を切り替えて外部依存なしで起動できる。

| 変数 | 既定 | 役割 |
|---|---|---|
| `FLOWNOTE_REPO_BACKEND` | `sql` | リポジトリ実装（`sql` / `memory`） |
| `FLOWNOTE_DATABASE_URL` | `sqlite+aiosqlite:///./.tmp/flownote.db` | SQLAlchemy 接続 URL |
| `FLOWNOTE_AI_BACKEND` | `stub` | AI 実装（`stub` / `openai`） |
| `FLOWNOTE_AI_BASE_URL` | `http://localhost:8001` | OpenAI 互換サーバ（[ai-mock](../ai-mock/README.md)） |
| `FLOWNOTE_AUTH_MODE` | `dev` | 認証方式（`dev` / `oidc`=Keycloak） |
| `FLOWNOTE_CORS_ORIGINS` | `http://localhost:3000` | 許可 CORS オリジン |

ローカル既定は **SQLite + AI スタブ + dev 認証**で外部依存ゼロ。compose では PostgreSQL / Keycloak / [ai-mock](../ai-mock/README.md) を使う。

## コマンド（リポジトリルートから / Python 3.14・uv）

```bash
uv sync                                   # 依存解決
uv run ruff format . && uv run ruff check --fix .   # フォーマット+リント
uv run mypy                               # 型チェック(strict)
uv run pytest                             # テスト
uv run --package flownote-api uvicorn flownote_api.main:app --reload   # 起動(:8000)
```

Docker: [`Dockerfile`](./Dockerfile)（マルチステージ・非 root・standalone venv）。compose 統合は [infra/](../../infra/) を参照。

## テスト（契約と境界を固定する）

[`tests/`](./tests/) に層別で配置。詳細設計書は作らず、契約はテストで固定する（[architecture.md §6](../../docs/architecture.md)）。

- `tests/domain` ドメインモデル / `tests/application` ユースケース / `tests/contracts` リポジトリ契約
- `tests/http` HTTP エンドポイント / `tests/observability` 可観測性規約（相関・マスキング・重大度・GenAI）

## 可観測性

ログは必ず `flownote_observability`（[packages/observability-py](../../packages/observability-py)）経由（`print` 禁止）。
FastAPI / SQLAlchemy / httpx を自動計装し、`ObservabilityMiddleware` が相関 ID と HTTP ログを担う。
AI 呼び出しは `GenAIInstrumentation` で計測する（[genai-observability.md](../../docs/observability/genai-observability.md)）。

エラーは `domain/errors.py` の `DomainError`（安定コード `code` / `http_status` / 外部公開タイトルを保持）で表現し、
HTTP 応答は **RFC 9457 Problem Details** に統一する。ログは「**境界で1度だけ**」記録する（[logging-spec §5](../../docs/observability/logging-spec.md)）。
`ADMIN` ロールは `PUT /admin/log-level` でプロセス再起動なしにログ閾値を変更できる（変更は監査ログに残る）。
