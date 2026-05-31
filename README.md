# FlowNote — ログ/可観測性システムの実証プロジェクト

> **このプロジェクトの主目的は「ログ/可観測性システムの構築と観察」です。** 題材アプリ FlowNote
> （Markdownメモ・タスク・バージョン管理を AI が支援する統合ワークスペース）は、フロント/バック/AI/
> 認証認可という多様なログ面を実際に発生させるための「器」であり、機能の作り込みより
> **各レイヤのログがどう設計・相関・収集されるか**の観察を優先しています。実験・学習用です。

## 何を学べるか

- **OpenTelemetry 準拠**で、ログ・トレース・メトリクスの3本柱を `trace_id`/`span_id` で相関させる方法
- フロント操作 → API → AI/DB/認証 までを**1つの trace** で横断追跡する構成
- **構造化ログ・マスキング・監査/セキュリティログ分離・GenAI(AI呼び出し)計装**の実装パターン
- 規約を文章ではなく**テストで固定**する（「テストこそ唯一の真実源泉」）進め方
- ベンダ非依存（OTLP → OTel Collector → SigNoz、ローカルは console/file exporter で代替）

可観測性の規約と設計は [`docs/observability/`](./docs/observability/) が一次資料です。まずは
[ログ規約(SSOT)](./docs/observability/logging-spec.md) と
[可観測性アーキテクチャ](./docs/observability/observability-architecture.md) を参照してください。

## アーキテクチャ概観

```
[Next.js(web)] --traceparent--> [FastAPI(api)] --> [PostgreSQL / Keycloak / AI(OpenAI互換 or mock)]
      |                              |
      +---- OTLP(trace/metric) ------+--> [OTel Collector] --> [SigNoz] / [console・file exporter]
   ログ(JSON)は標準出力 → docker logs / コンソール（本番は stdout 集約 agent）
```

- 契約と境界：インターフェース(Protocol/interface) + ドメインモデル、境界は Pydantic/型で検証。
- 一方向依存（レイヤード）：`interface → application → domain`、`infrastructure → application/domain`。**domain は外向き依存ゼロ**。
- 詳細は [docs/architecture.md](./docs/architecture.md)、技術判断は [docs/adr/](./docs/adr/)、コンセプトは [docs/concept.md](./docs/concept.md)。

## モノレポ構成

```
apps/
  api/        FastAPI バックエンド（domain/application/infrastructure/interface）
  web/        Next.js 16 フロントエンド（App Router / Auth.js / デザイントークン）
  ai-mock/    OpenAI互換モックサーバ（開発用・vLLM代替）
packages/
  observability-py/   共有: 構造化ログ/OTel/相関/マスキング/GenAI計測（中核）
  observability-web/  共有: ブラウザ計装/クライアントロガー/traceparent
infra/        docker-compose / otel-collector / keycloak realm / Dockerfile
docs/         設計・規約    .claude/skills/  再利用スキル    CLAUDE.md  作業ガイド
```

- Python は **uv ワークスペース**、TypeScript は **pnpm ワークスペース**。

## 必要環境

- Python 3.14（[uv](https://docs.astral.sh/uv/) で管理）
- Node.js 20+ / [pnpm](https://pnpm.io/) 9+
- Docker（インフラ一式を使う場合。アプリ単体はローカル実行のみで可）

## クイックスタート

外部依存なし（SQLite + AIスタブ + dev認証）でバックエンドを起動し、ログを観察できます。

```bash
# 依存解決
uv sync --all-packages
pnpm install

# バックエンド起動（トレース/メトリクスをコンソールにも出す）
FLOWNOTE_OTEL_CONSOLE=1 uv run --package flownote-api uvicorn flownote_api.main:app --reload

# 動作確認（dev認証トークン <sub>:<role> を付与）
curl localhost:8000/health
curl -X POST localhost:8000/api/notes \
  -H "Authorization: Bearer alice:editor" -H "Content-Type: application/json" \
  -d '{"title":"買い物","body":"りんごを買う"}'
curl -X POST localhost:8000/api/ai/search \
  -H "Authorization: Bearer alice:editor" -H "Content-Type: application/json" \
  -d '{"query":"りんご"}'
```

標準出力に1行JSONの構造化ログが流れ、`trace_id` で相関した
アクセスログ・業務イベント・監査ログ・GenAI 計測を観察できます。

### フロントエンド

```bash
pnpm --filter web dev          # http://localhost:3000
```

### 観測スタック / 実サービス（任意）

```bash
# PostgreSQL / Keycloak / OTel Collector / AIモック
docker compose -f infra/compose.yaml up -d postgres keycloak otel-collector ai-mock
# SigNoz を含める場合（重量級・ベストエフォート）
docker compose -f infra/compose.yaml --profile signoz up -d
```

OTLP 送出先を指定するとトレース/メトリクスが Collector に届きます：

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
  uv run --package flownote-api uvicorn flownote_api.main:app --reload
```

詳細・環境変数は [infra/README.md](./infra/README.md) と [.env.example](./.env.example) を参照。

## 開発コマンド

| 目的 | コマンド |
|---|---|
| バックエンド: テスト | `uv run pytest` |
| バックエンド: 整形+リント | `uv run ruff format . && uv run ruff check .` |
| バックエンド: 型チェック | `uv run mypy` |
| フロント: テスト | `pnpm -r test` |
| フロント: 整形+リント | `pnpm exec biome check --write .` |
| フロント: 型チェック | `pnpm --filter web typecheck` |
| フロント: 本番ビルド | `pnpm --filter web build` |

## 技術スタック

- **バックエンド**: Python 3.14 / FastAPI / Pydantic / SQLAlchemy 2.0(async) / structlog / OpenTelemetry / pytest / ruff / mypy(strict)
- **フロントエンド**: TypeScript / Next.js 16 / Auth.js(Keycloak OIDC) / Biome / vitest / Storybook
- **データ/認証/AI**: PostgreSQL（ローカルは SQLite）/ Keycloak / OpenAI互換（開発はモック、想定は vLLM 上の qwen・gemma）
- **可観測性**: OpenTelemetry + OTel Collector + SigNoz（ローカルは console/file exporter）

## ドキュメント

- [CLAUDE.md](./CLAUDE.md) — リポジトリ作業ガイド（規約・コマンド・構成の入口）
- [docs/observability/](./docs/observability/) — **ログ/可観測性の規約（中核）**
- [docs/architecture.md](./docs/architecture.md) / [docs/concept.md](./docs/concept.md) / [docs/adr/](./docs/adr/)
- [.claude/skills/](./.claude/skills/) — 再利用スキル（共通ログ設計 / git戦略 / レビュー基準 / デザイントークン）

## 既知の制約

- **Next.js 16 / Auth.js v5 は現状 beta** を採用（v16 安定版が未リリースのためのフォールバック）。
- SigNoz(ClickHouse)・vLLM は重く、環境によっては完全起動が難しいため、観察は **console/file exporter と AIモック**を基本線にしています。
- Auth.js のトークンリフレッシュは未実装（学習用途のため簡略化）。

## ライセンス

学習・実験目的のサンプルプロジェクトです。
