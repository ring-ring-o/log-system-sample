# infra — ローカル実行と可観測性スタック

> 主目的は[ログ/可観測性の観察](../docs/observability/observability-architecture.md)。開発時はアプリを
> ローカルコマンドで起動してもよく(コンテナにこだわりすぎない)、観測スタックのみ compose で立てる運用を推奨する。

## 構成

| サービス | 役割 | ポート |
|---|---|---|
| postgres | アプリDB(本番/compose) | 5432 |
| keycloak | OIDC IdP(realm: flownote を import) | 8080 |
| otel-collector | OTLP受信→整形→debug/file(/任意でSigNoz) | 4317/4318 |
| ai-mock | OpenAI互換モック(vLLM代替) | 8001 |
| api | FastAPI バックエンド | 8000 |
| web | Next.js フロントエンド | 3000 |
| clickhouse | SigNoz用(profile: signoz) | 9000 |

## 最小起動(観測スタック + 周辺)

```bash
docker compose -f infra/compose.yaml up -d postgres keycloak otel-collector ai-mock
```

アプリはローカルで(ホットリロード):

```bash
# API(sqlite + AIスタブ + dev認証なら外部不要)
uv run --package flownote-api uvicorn flownote_api.main:app --reload
# OTLP に送る場合
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
  uv run --package flownote-api uvicorn flownote_api.main:app --reload

# AIモック
uv run --package flownote-ai-mock uvicorn flownote_ai_mock.main:app --port 8001

# フロント
pnpm --filter web dev
```

## ログ/トレース/メトリクスの観察

- **コンソール**: `FLOWNOTE_OTEL_CONSOLE=1` でトレース/メトリクスを標準出力にも出力。構造化ログは常に標準出力(JSON)。
- **Collector経由**: `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` を設定するとトレース/メトリクスが Collector に届き、
  `./volumes/otel-output/otel-output.jsonl`(file exporter)と Collector ログ(debug exporter)で確認できる。
- **相関**: ログとトレースは `trace_id`/`span_id` で結びつく。1リクエストの `trace_id` で横断追跡できる。

## SigNoz(任意・重量級)

SigNoz は ClickHouse を含み重い。完全構成は[公式デプロイ](https://signoz.io/docs/install/docker/)を参照。
本リポジトリでは収集経路の確認用に最小限のみ用意し、`--profile signoz` で関連サービスを起動する。
有効化時は `otel-collector/config.yaml` の各パイプライン exporters に `otlp/signoz` を追加する。

```bash
docker compose -f infra/compose.yaml --profile signoz up -d
```

## Keycloak

- 管理コンソール: http://localhost:8080 (admin/admin)
- realm `flownote` を起動時に import。テストユーザー: `alice`(editor) / `admin-user`(admin) / `viewer-user`(viewer)、いずれもパスワード `password`。
- API は `FLOWNOTE_AUTH_MODE=oidc` で JWKS 検証に切り替わる。ローカル簡易実行は `dev`(Keycloak不要)。

## 注意

- `volumes/` はローカル状態であり `.gitignore` 済み。
- 当環境(CI/サンドボックス)ではイメージ取得や SigNoz/vLLM の完全起動が不確実なため、観察は
  コンソール/ファイル exporter を基本線とする([ADR 0002](../docs/adr/0002-signoz.md))。
