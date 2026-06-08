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

## フルスタック起動(api/web 込みで compose 一括)

アプリ(`api`)とフロント(`web`)もコンテナで立ち上げ、観測スタックまで含めて一括で動かす場合。
`compose.yaml` の `api`/`web` は `depends_on` で `postgres`/`ai-mock`/`otel-collector` を待つため、
サービス名を列挙せず**全サービスを起動**すればよい(初回はイメージ build が走る)。

```bash
# 観測スタック + api + web を含む全サービスを起動(build 込み)。
docker compose -f infra/compose.yaml up -d --build

# 起動状況とヘルスを確認。
docker compose -f infra/compose.yaml ps
```

- アクセス: web=http://localhost:3000 / api=http://localhost:8000 / keycloak=http://localhost:8080。
- 停止: `docker compose -f infra/compose.yaml down`(データ込みで消すなら `-v` を付与。ただし `volumes/` は別途残る)。
- このモードでは `api`/`web` は**コンテナ内**で動くため、ローカルコマンド起動とはログの出所が変わる(下記)。
- 既定の `api` コンテナは `FLOWNOTE_ENV=dev`・`FLOWNOTE_AUTH_MODE=oidc`(Keycloak 検証)で動く。
  認証を介さず疎通だけ見たい場合は `compose.yaml` の `api.environment` で `FLOWNOTE_AUTH_MODE=dev` に上書きする。

## ログ/トレース/メトリクスの観察

可観測性は **2 つの面**に分かれる。①構造化ログ(JSON)は各プロセスの**標準出力**に出る。
②トレース/メトリクス(と任意でログ)は **OTLP** で otel-collector に送られ、`debug`/`file` exporter で確認する。
どこを見るかは「ローカルコマンド起動」か「フルスタック compose 起動」かで変わる。

### ① 構造化ログ(JSON / 標準出力)

- **ローカルコマンド起動**: 各コマンドを実行した**ターミナルの標準出力**に直接出る。
- **フルスタック compose 起動**: コンテナの標準出力に出るため、Docker のログドライバ経由で集約する。

  ```bash
  # 全サービスを追従(JSON ログ)。
  docker compose -f infra/compose.yaml logs -f

  # api / web に絞って追従。
  docker compose -f infra/compose.yaml logs -f api web
  ```

  実体は各コンテナの json-file ログ(ホストの `/var/lib/docker/containers/<id>/<id>-json.log`)。
  本番ではこの**標準出力を tail する agent**(filelog receiver / Fluent Bit 等)で集約する想定(12-factor、
  [ADR 0005](../docs/adr/0005-log-transport.md))。compose でこの集約まで再現したい場合は後述「ログを Collector に集約する」を参照。

### ② トレース/メトリクス(OTLP → otel-collector)

- 送出先は環境変数 `OTEL_EXPORTER_OTLP_ENDPOINT` で決まる。
  - ローカルコマンド起動: `http://localhost:4318`(ホストから Collector へ)。
  - フルスタック compose 起動: `api` コンテナは compose ネットワーク内の `http://otel-collector:4318`(`compose.yaml` に設定済み)。
- web の**ブラウザ側**ログ/トレースは `NEXT_PUBLIC_OTLP_ENDPOINT`(既定 `http://localhost:4318`)へ beacon/fetch で送る。
  ブラウザはホスト上で動くため、コンテナ起動でもホストの `localhost:4318`(= Collector の公開ポート)を指す。
- Collector に届いたデータの確認先:
  - **file exporter**: `./volumes/otel-output/otel-output.jsonl`(`tail -f` で観察)。
  - **debug exporter**: `docker compose -f infra/compose.yaml logs -f otel-collector`。
- **相関**: ①のログと②のトレースは `trace_id`/`span_id` で結びつく。1リクエストの `trace_id` で①②を横断追跡できる。

### ログを Collector に集約する(任意・compose での本番相当の集約)

標準出力の JSON ログまで otel-collector に集約したい場合は、Collector に **filelog receiver** を追加し、
コンテナの json-file ログを読み取らせる(`docker compose logs` で十分なら不要)。
`otel-collector/config.yaml` に以下を追記する例:

```yaml
receivers:
  filelog:
    include: [/var/lib/docker/containers/*/*-json.log]
    operators:
      # Docker json-file ドライバの 1 行 = {"log":"...","stream":"...","time":"..."}。
      - type: json_parser
      # アプリが出す構造化ログ本体(JSON 文字列)をさらに展開する。
      - type: json_parser
        parse_from: attributes.log
service:
  pipelines:
    logs:
      receivers: [otlp, filelog]   # OTLP に加えて標準出力ログも取り込む
      processors: [memory_limiter, resource, batch]
      exporters: [debug, file]
```

併せて `compose.yaml` の `otel-collector` に
`- /var/lib/docker/containers:/var/lib/docker/containers:ro` をボリュームマウントする。
これでコンテナ標準出力の JSON ログも `./volumes/otel-output/otel-output.jsonl` に集約される。
（ホストの Docker ログパスは環境差があるため、確実に観察したいだけなら `docker compose logs` を基本線とする。）

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
