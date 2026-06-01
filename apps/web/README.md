# apps/web — FlowNote フロントエンド (Next.js 16)

FlowNote の Web フロントエンド。Markdown メモ・タスク・バージョン管理を AI が支援する統合ワークスペースの UI で、
**App Router / React 19 / Auth.js v5（Keycloak OIDC）**で構成し、操作を API までつなぐ
**1 つの trace** の起点（`traceparent` 伝播）となる。

> このアプリは題材であり、真の成果物は可観測性システムである。フロントのログ/計装は
> [frontend-logging.md](../../docs/observability/frontend-logging.md) を一次資料とする。

## 構成

```
src/
  app/            App Router（layout.tsx / page.tsx / globals.css / api/auth/[...nextauth]）
  auth.ts         Auth.js v5 設定（Keycloak OIDC・アクセストークンをセッションへ）
  components/     共有 UI（Button + Storybook/テスト・Providers）
  features/       機能 UI（notes / dashboard / ai 検索パネル）
  shared/         api-client / observability（ClientLogger） / use-token
  tokens/         デザイントークン（semantic 層のみ参照する）
  types/          型拡張（next-auth.d.ts 等）
```

- **デザイントークン**: UI は semantic 層のトークンのみ参照し、生値の直書きは禁止
  （[design-tokens スキル](../../.claude/skills/design-tokens/SKILL.md)）。
- **認証**: Keycloak でログインし、アクセストークンをセッションに載せて API 呼び出しに用いる
  （[ADR 0004](../../docs/adr/0004-auth-keycloak.md)）。

## コマンド（リポジトリルートから / pnpm）

```bash
pnpm install
pnpm biome check --write .       # フォーマット+リント
pnpm --filter web dev            # 開発サーバ(:3000)
pnpm --filter web build          # ビルド(standalone)
pnpm --filter web test           # vitest
pnpm --filter web typecheck      # tsc --noEmit
pnpm --filter web storybook      # Storybook(:6006)
```

Docker: [`Dockerfile`](./Dockerfile)（`output: "standalone"` 前提・マルチステージ・非 root）。

## 環境変数

| 変数 | 役割 |
|---|---|
| `AUTH_KEYCLOAK_ID` / `AUTH_KEYCLOAK_SECRET` / `AUTH_KEYCLOAK_ISSUER` | Keycloak OIDC クライアント設定 |
| `NEXT_PUBLIC_OTLP_ENDPOINT` | クライアントログ/トレースの送信先（未設定時は console フォールバック） |
| `NEXT_PUBLIC_DEPLOYMENT_ENV` | 実行環境ラベル（既定 `local`） |
| `NEXT_PUBLIC_API_BASE_URL` | バックエンド API のベース URL |

## 可観測性

ログ/トレースは必ず `@flownote/observability-web`（[packages/observability-web](../../packages/observability-web)）経由（`console.log` 直出力禁止）。
`Providers` がページ単位のルートトレースを開始し、Web Vitals 収集・グローバルエラーハンドラを初期化する。
fetch は `traceparent` を付与して API と同一 trace に束ねる。

## 注意

Next.js 16 / Auth.js v5 は安定版未リリースのため **beta を採用**（[CLAUDE.md §9](../../CLAUDE.md)）。安定版リリース後に更新する。
