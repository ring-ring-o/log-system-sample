# CLAUDE.md — FlowNote モノレポ作業ガイド

このファイルは Claude Code（および開発者）が本リポジトリで作業する際の規約・コマンド・参照先をまとめた最初の入口である。

## 0. このプロジェクトの主目的（最重要）

**本プロジェクトの真の成果物は「ログ/可観測性システムとその規約」である。** 題材アプリ FlowNote（メモ/タスク/バージョン管理/AI/認証）は、多様なログ面を発生させる器にすぎない。実装の判断に迷ったら **「可観測性の規約準拠・観察可能性」を最優先**する（[concept.md](./docs/concept.md) §7 の品質優先順位）。

## 1. 必読ドキュメント

| いつ読むか | ドキュメント |
|---|---|
| **まず計装の書き方を知りたい（DX）** | [docs/observability/logging-cookbook.md](./docs/observability/logging-cookbook.md)（「やりたいこと → こう書く」。`operation`/`log_event`/`DomainError`。規約の暗記は不要） |
| ログ実装・レビュー時（常時） | [docs/observability/logging-spec.md](./docs/observability/logging-spec.md)（**規約=SSOT**） |
| 可観測性の全体像 | [docs/observability/observability-architecture.md](./docs/observability/observability-architecture.md) |
| AI実装時 | [docs/observability/genai-observability.md](./docs/observability/genai-observability.md) |
| 認証認可実装時 | [docs/observability/audit-logging.md](./docs/observability/audit-logging.md) |
| ログ出力を書くとき | [docs/observability/redaction-policy.md](./docs/observability/redaction-policy.md) / [frontend-logging.md](./docs/observability/frontend-logging.md) |
| 設計判断 | [docs/architecture.md](./docs/architecture.md) / [docs/adr/](./docs/adr/) |

スキル（`.claude/skills/`）: `observability-logging` / `git-workflow` / `code-review-standards` / `design-tokens`。該当作業時に必ず参照する。

## 2. モノレポ構成

```
apps/api          FastAPIバックエンド（レイヤード: domain/application/infrastructure/interface）
apps/web          Next.js 16 フロントエンド
apps/ai-mock      OpenAI互換モックサーバ（開発用）
packages/observability-py    共有: 構造化ログ/OTel/相関/マスキング/GenAI計測（中核）
packages/observability-web   共有: ブラウザ計装/クライアントロガー
infra             docker-compose / otel-collector / keycloak / signoz(profile起動・最小)
docs              設計・規約    .claude/skills 再利用スキル
```

- Python: **uv workspace**（ルート `pyproject.toml`）。TS: **pnpm workspace**（`pnpm-workspace.yaml`）。
- 依存方向は一方向（`interface→application→domain`、`infrastructure→application/domain`）。**domain は外向き依存ゼロ**。

## 3. コマンド

### バックエンド（Python 3.14 / uv）
```bash
uv sync                                   # 依存解決
uv run ruff format . && uv run ruff check --fix .   # フォーマット+リント
uv run mypy                               # 型チェック（strict）
uv run pytest                             # テスト
uv run --package flownote-api uvicorn flownote_api.main:app --reload   # API起動
uv run --package flownote-ai-mock uvicorn flownote_ai_mock.main:app --port 8001  # AIモック
```

### フロントエンド（pnpm）
```bash
pnpm install
pnpm biome check --write .                # フォーマット+リント
pnpm --filter web dev                     # 開発サーバ
pnpm --filter web build                   # ビルド
pnpm --filter web test                    # vitest
pnpm --filter web storybook               # Storybook
```

### インフラ（ベストエフォート）
```bash
docker compose -f infra/compose.yaml up -d postgres keycloak otel-collector ai-mock  # 観測スタック+周辺のみ
docker compose -f infra/compose.yaml up -d --build            # api/web 込みで一括起動（フルスタック）
docker compose -f infra/compose.yaml logs -f api web          # コンテナ標準出力のJSONログを追従
docker compose -f infra/compose.yaml --profile signoz up -d   # SigNozは重い
```
ログの出所（コンテナ標準出力 / OTLP→otel-collector）と集約設定は [infra/README.md](./infra/README.md) を参照。

## 4. コーディング規約（バックエンド）

- Python **3.14**。`Dict`/`List`/`Optional` は使わず **`dict`/`list`/`X | None`** を用いる。
- `Any`/`object` は**極力使わない**（境界外は具体型 or Protocol / ジェネリクス）。
- **型ヒント必須**。境界の入出力は **Pydantic** で定義・検証。ドメインモデルは純粋な dataclass/値オブジェクト（フレームワーク非依存）。
- **日本語の Google スタイル docstring を必須**付与（Args/Returns/Raises）。意図の説明コメントも日本語で適宜。
- **宣言的**に書く（早期return・純粋関数・不変データ）。
- ツール: **ruff**(format+lint) / **mypy**(strict) / **pytest**。
- ログは必ず `packages/observability-py` 経由（[ログ規約](./docs/observability/logging-spec.md)準拠）。`print` 禁止。

## 5. コーディング規約（フロントエンド）

- **TypeScript**（厳密設定）。**biome**(format+lint)。**pnpm**。
- **Next.js 16**(App Router)。テスト **vitest**、コンポーネントは **Storybook**。
- 日本語ドキュメンテーションコメント＋意図コメントを付与。
- UIは[デザイントークン](./.claude/skills/design-tokens/SKILL.md)の semantic 層のみ参照（生値直書き禁止）。
- ログ/トレースは `packages/observability-web` 経由。`console.log` 直出力禁止。

## 6. テスト方針（唯一の真実源泉）

詳細設計書は作らない。**契約と境界はテストで固定**する（[architecture.md §6](./docs/architecture.md)）。
- `tests/domain` `tests/application` `tests/contracts` `tests/observability` `tests/http`。
- 新機能は**まずテストで契約を書く**。可観測性規約（相関/マスキング/重大度/監査/GenAI）は必ずテスト化。

## 7. git 規約（[git-workflow スキル](./.claude/skills/git-workflow/SKILL.md)）

- コミットは**機能単位**。prefix は **`add`/`update`/`fix`/`delete`** のみ。
- **GitHub flow**: `main` から `feat/*`・`fix/*` を切り、`--no-ff` で統合、ブランチ削除。
- push はユーザー明示時のみ。秘密・生成物はコミットしない（`.gitignore`）。
- コミット末尾に `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. レビュー（実装完了後・必須・別コンテキスト）

実装完了後は必ず[code-review-standards スキル](./.claude/skills/code-review-standards/SKILL.md)基準でレビューする。**レビューは別コンテキスト（サブエージェント or `/code-review`）で実施**し、指摘を反映する。

## 9. 環境メモ

- Python 3.14 は uv 管理。ライブラリは最新安定版（3.14非対応なら近接版にフォールバックし理由を記録）。
- **Next.js 16 / Auth.js v5 は現状 beta を採用**（v16 の安定版が未リリースのため。要件「v16 の最新安定版」に対するフォールバックとして記録）。安定版リリース後に更新する。
- AI は OpenAI互換。開発時は `apps/ai-mock` を使用（vLLMは重いため）。
- SigNoz/ClickHouse は重く完全起動は不確実 → console/file exporter で観察を担保。
- ログは標準出力(JSON)、トレース/メトリクスは OTLP。本番のログ集約は stdout を tail する agent を想定。
