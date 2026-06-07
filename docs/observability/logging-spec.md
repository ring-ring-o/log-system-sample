# ログ規約（Logging Specification） — 唯一の真実源泉(SSOT)

> 本書は当モノレポ全体（バックエンド/フロントエンド/AI/認証認可/インフラ）に適用される**ログの唯一の規約**である。
> 各実装はこの規約を満たさなければならず、規約への準拠は**テスト**（`apps/api/tests/observability/` 等）によって固定される。
> 関連文書: [ログ・クックブック(開発者DX)](./logging-cookbook.md) / [可観測性アーキテクチャ](./observability-architecture.md) / [GenAI可観測性](./genai-observability.md) / [監査ログ](./audit-logging.md) / [マスキング規約](./redaction-policy.md) / [フロントエンドログ](./frontend-logging.md)
>
> **実装する前に**: 規約の暗記は不要。まず [クックブック](./logging-cookbook.md) の「やりたいこと → こう書く」を見て、`operation`/`log_event`/`DomainError` を使う。規約はファサードとテストが守る。

## 0. 用語と前提

| 用語 | 定義 |
|---|---|
| シグナル(signal) | 可観測性の信号。**ログ / トレース / メトリクス** の3本柱を指す。 |
| ログ(log) | ある時点で発生した事象の構造化レコード（本書の主対象）。 |
| トレース(trace) | 1リクエスト等の処理全体。複数の span から成る。`trace_id` で識別。 |
| span | トレース内の1処理単位。`span_id` で識別。ログは span に相関する。 |
| 相関(correlation) | ログ・トレース・メトリクスを共通キー（`trace_id` 等）で結びつけること。 |

**統一規格は [OpenTelemetry](https://opentelemetry.io/)（以下 OTel）。** ログのデータモデル・属性命名・重大度は OTel の仕様に準拠する。これにより特定ベンダ（SigNoz / Datadog / Grafana 等）に固定されない。

## 1. 基本原則

1. **構造化ログのみ**（JSON Lines）。人間可読の整形は閲覧ツール側（コンソール/SigNoz）の責務であり、出力は常に機械可読とする。
2. **1イベント1行**。複数行スタックトレースも1レコードの `exception.stacktrace` フィールドに格納する。
3. **相関必須**。アプリケーションログは必ず実行中の span から `trace_id`/`span_id` を継承する。
4. **意味づけは属性で**。メッセージ文字列に可変値を埋め込まない（×`f"user {id} login"`）。固定メッセージ＋構造化属性とする（○`message="user login", attributes={"user.id": id}`）。これによりログの集計・検索・アラートが可能になる。
5. **機密は出さない**。[マスキング規約](./redaction-policy.md)に従い、PII・認証情報を必ず除去/マスクする。
6. **コストを意識する**。ログは無料ではない。レベルとサンプリングで量を制御する（§7,§8）。

## 2. ログレコード・スキーマ

すべてのログは以下のスキーマに正規化される（OTel Logs Data Model 準拠）。Pydanticモデル `packages/observability-py/.../schema.py::LogRecord` を唯一の実装とする。

### 2.1 必須フィールド（トップレベル）

| フィールド | 型 | 説明 | 例 |
|---|---|---|---|
| `timestamp` | string(RFC3339, nano) | 事象発生時刻（UTC）。 | `2026-05-31T12:34:56.789012345Z` |
| `severity_text` | string | 重大度ラベル（§3）。 | `INFO` |
| `severity_number` | int | OTel重大度番号（§3）。 | `9` |
| `body` | string | 固定のイベント名/メッセージ。低カーディナリティに保つ。 | `http.request.completed` |
| `flownote.log.schema_version` | string | ログスキーマ世代。規約進化時に ETL/パース側が判別できるよう必須。 | `1` |
| `service.name` | string | 発生元サービス。 | `flownote-api` |
| `service.version` | string | デプロイ識別。 | `0.1.0` |
| `deployment.environment.name` | string | `local`/`dev`/`staging`/`prod`（OTel Stable の rename 後の名。旧 `deployment.environment` は使わない）。 | `local` |
| `trace_id` | string(hex32) \| null | 相関トレースID。span外なら null。 | `4bf92f3577b34da6...` |
| `span_id` | string(hex16) \| null | 相関spanID。 | `00f067aa0ba902b7` |
| `attributes` | object | 構造化属性（§4）。 | `{"http.response.status_code": 200}` |

### 2.2 推奨フィールド（`attributes` 内 or トップレベル拡張）

- `request_id`: HTTPリクエスト単位のID（クライアント発行 or サーバ採番）。trace_idと別に保持し、trace未生成区間でも追跡可能にする。
- `session_id`: 認証セッション識別子（[マスキング規約](./redaction-policy.md)に従いハッシュ化）。

> **`request_id` と `trace_id` の住み分け**（混同しやすいので明記）:
> - `trace_id`: OTel span が生成された区間でのみ存在する。span 外（採番前/採番後の境界外処理）では `null`。
> - `request_id`: フロント発行 or LB/CDN/サーバ採番で、**span 生成前**から付く。span が無い区間（例: ミドルウェア最外や span 生成失敗時）でも一貫して追跡できる「人間が口頭で伝えやすい」軸。
> - 実運用: ユーザーがサポートに伝えるのは応答ヘッダ/Problem Details の `trace_id`（トレース引き戻し用）。`request_id` はアプリ内の補助相関に用いる。
- `user.id`: 認証主体（Keycloak `sub`）。**メール等PIIではなく不透明IDを使う**。
- `code.namespace` / `code.function`: 発生箇所。
- `event.domain`: ログの分類（`app` / `audit` / `security` / `access` / `genai`）。

### 2.3 出力例（1行JSON、整形表示）

```json
{
  "timestamp": "2026-05-31T12:34:56.789012345Z",
  "severity_text": "INFO",
  "severity_number": 9,
  "body": "http.request.completed",
  "service.name": "flownote-api",
  "service.version": "0.1.0",
  "deployment.environment.name": "local",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "attributes": {
    "event.domain": "access",
    "request_id": "01J...",
    "user.id": "f47ac10b-58cc-...",
    "http.request.method": "POST",
    "http.route": "/api/notes",
    "http.response.status_code": 201,
    "http.server.request.duration": 0.0427
  }
}
```

### 2.4 `body` とイベント名（将来の `event.name` 移行）

本規約は `body` に**固定イベント名**（`http.request.completed` 等）を入れる方式を採る（structlog の `event` に近い）。OTel Logs Data Model 本来の `body` は「人間可読メッセージ」で、近年は **`event.name` 属性にイベント名・`body` に自然言語**を入れる流派が増えている（SigNoz/Grafana の新しい UI は `event.name` 前提が増加）。

- 現状: 一貫して `body`=イベント名で運用（集計軸として機能しており問題なし）。
- 将来: `event.name` へ移行する場合は `flownote.log.schema_version` を上げ、両対応期間を設ける。移行判断は ADR 化する。

## 3. 重大度（Severity）

OTel `SeverityNumber` に一対一で対応させる。アプリは下表の6レベルのみを用いる（OTelの細分は使わない）。

| ラベル | OTel番号 | 用途 | 例 |
|---|---|---|---|
| `TRACE` | 1 | 最も詳細な開発用。本番では無効。 | ループ内部状態 |
| `DEBUG` | 5 | 開発・調査用の詳細。 | クエリパラメータ、分岐 |
| `INFO` | 9 | 正常な業務イベント。 | リクエスト完了、メモ作成 |
| `WARN` | 13 | 異常ではないが注意すべき事象。回復可能。 | リトライ発生、レート制限接近、非推奨API使用 |
| `ERROR` | 17 | 処理が失敗。当該リクエスト/ジョブは不成立。 | 4xxではなく未捕捉例外、5xx、AI呼び出し失敗 |
| `FATAL` | 21 | プロセス継続不能。 | 起動時必須設定の欠落、DB接続不可で起動失敗 |

ルール:
- **4xx は2段階**で扱う（一律 WARN にすると健全な利用でもアラート閾値近くまで上がり、慣れて無視されるため）:
  - **期待される失敗（Expected）= `INFO`**: バリデーション失敗(422)、未存在(404)、競合(409) などクライアントの仕様内動作。
  - **異常/攻撃シグナル（Unexpected）= `WARN`**: 認証失敗(401)、認可拒否(403)、レート制限(429)、426/428 など。認可拒否は加えて `audit`+`WARN`。
  - 実装は `severity_for_http_status`（WARN 集合を `_WARN_CLIENT_ERRORS` で定義）を唯一の源泉とする。
- **5xx と未捕捉例外は `ERROR`**。
- `ERROR` 以上には必ず `exception.*` 属性（§5）を付ける。
- アラート閾値は `severity_number >= 17`（ERROR）を基準に設計する。

## 4. 属性命名規約（Semantic Conventions）

OTel [Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/) に準拠する。**独自属性は最終手段**とし、既存規約を最優先で用いる。

### 4.1 採用する標準名前空間

| 名前空間 | 用途 | 主なキー |
|---|---|---|
| `http.*` | HTTPサーバ/クライアント | `http.request.method`, `http.route`, `http.response.status_code`, `http.server.request.duration`（**単位は秒** `s`、UCUM準拠。`*_ms` は使わない） |
| `db.*` | データベース | `db.system`(=`postgresql`), `db.operation.name`, `db.collection.name` |
| `user.*` | 認証主体 | `user.id`, `user.roles`（PIIは禁止、§[マスキング](./redaction-policy.md)） |
| `gen_ai.*` | 生成AI | [GenAI可観測性](./genai-observability.md)参照 |
| `exception.*` | 例外 | `exception.type`, `exception.message`, `exception.stacktrace` |
| `code.*` | コード位置 | `code.namespace`, `code.function`, `code.lineno` |

### 4.2 独自名前空間

アプリ固有属性は `flownote.*` 配下に置く（衝突回避）。

- `flownote.note.id`, `flownote.task.id`, `flownote.task.status`, `flownote.version.id`, `flownote.search.query_hash` 等。
- **クエリ本文や本文テキストはそのまま入れない**。`*.query_hash` のようにハッシュ化/要約する（カーディナリティとPII対策）。

### 4.3 カーディナリティ規約

- `body`（イベント名）と低カーディナリティ属性（method, status, route テンプレート）は**集計軸**。ID等の高カーディナリティ値は**属性値**として保持し、`body` には埋めない。
- `http.route` は `/api/notes/{note_id}` のような**テンプレート**を用い、実IDは `flownote.note.id` に分離する。

## 5. 例外・エラーログ

`ERROR`/`FATAL` では以下を必須とする（OTel `exception.*`）。

| 属性 | 内容 |
|---|---|
| `exception.type` | 例外クラス完全名（`flownote.domain.errors.NoteNotFoundError`）。 |
| `exception.message` | 例外メッセージ（PII混入に注意、[マスキング](./redaction-policy.md)適用）。 |
| `exception.stacktrace` | スタックトレース文字列。 |

- ドメイン例外は型で分類し、`event.domain="app"`。インフラ例外（DB/AI/ネットワーク）は原因 span にも記録（span status=ERROR）。
- 例外は**握りつぶさない**。捕捉して継続する場合は最低 `WARN` でログし、理由属性を付す。

### 5.1 エラーコードと内部/外部メッセージ分離

`exception.type`（クラス完全名）は内部実装の都合で変わりうるため、**公開 API の識別子には使わない**。代わりに**安定したエラーコード** `flownote.error.code`（例 `RES.NOT_FOUND` / `AUTHZ.DENIED` / `VAL.INVALID`）を1つ持たせる。実装は `apps/api/.../domain/errors.py::DomainError` を唯一の源泉とし、`error_catalog()` でコード ↔ 意味 ↔ HTTP status を列挙できる。

ドメイン例外は文言を構造的に分離する（機密のクライアント漏洩防止）:

| 区分 | フィールド | 行き先 |
|---|---|---|
| 公開 | `code` / `public_title` / `public_detail` | クライアント応答（Problem Details）＋ログ |
| 内部 | `internal_context`（内部ID・原因・SQL等） | **ログのみ**（応答には載せない） |

**コードの命名規則**: `<DOMAIN>.<NAME>`（ともに大文字）。`DOMAIN` は意味領域の接頭辞、`NAME` はその中の具体事象。クラス名は変えてもコードは変えない（公開 API の契約）。現行の接頭辞:

| 接頭辞 | 意味領域 | 例 | 主な HTTP |
|---|---|---|---|
| `RES` | リソースの状態（存在/競合） | `RES.NOT_FOUND` / `RES.CONFLICT` | 404 / 409 |
| `VAL` | 入力検証 | `VAL.INVALID`（ドメイン不変条件） / `VAL.REQUEST`（スキーマ違反） | 422 |
| `AUTH` | 認証（本人性） | `AUTH.UNAUTHORIZED` | 401 |
| `AUTHZ` | 認可（権限） | `AUTHZ.DENIED` | 403 |
| `GEN` | 汎用・未識別のフォールバック | `GEN.INTERNAL` | 500 |

新しい意味領域が必要になったら接頭辞を1つ足し、本表に追記する（例: `RATE`／`DEP`〔依存先障害〕等）。

**抽出（自動）**: クライアントに返る全公開コードは2源泉に分かれる — ①ドメイン例外（`domain/errors.py`、`error_catalog()`、基底 `GEN.INTERNAL` 含む）と、②境界が直接発行するコード（`interface/http/error_catalog.py` の SSOT。`AUTH.UNAUTHORIZED` / `VAL.REQUEST`）。両者を統合した完全カタログは `full_error_catalog()`、コマンドは `flownote-error-catalog`（Markdown/JSON/CSV/**TS**/`--check`）。生成物は [error-catalog.md](./error-catalog.md)、使い方は [apps/api README](../../apps/api/README.md)。

**フロント共有**: フロントはコード集合を手書きせず、`--format ts` で `apps/web/src/shared/error-catalog.generated.ts`（`ErrorCode` union / `ERROR_CATALOG`）を生成して参照する。これによりバック↔フロントでコード集合が一致し、クライアントは安定 `code` で分岐できる（[frontend-logging §3.1](./frontend-logging.md)）。

### 5.2 クライアント応答は RFC 9457 Problem Details

API がクライアントへ返すエラー本文は `application/problem+json`（[RFC 9457](https://www.rfc-editor.org/rfc/rfc9457)）に統一する。実装は `apps/api/.../interface/http/problem.py`。

```json
{
  "type": "https://errors.flownote.example/RES.NOT_FOUND",
  "title": "リソースが見つかりません",
  "status": 404,
  "code": "RES.NOT_FOUND",
  "detail": "note が見つかりません",
  "instance": "/api/notes/abc",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"
}
```

- `code`: クライアントは可変メッセージではなく**コードで分岐**する。
- `trace_id`: エンドユーザーがサポートへ伝えれば、サポートが SigNoz でトレースを引き戻せる。

### 5.3 エラーは「境界で1度だけ」ログる

**ドメイン/アプリケーション層は失敗時に例外を `raise` するだけ**でログしない。ログは **interface 層の最外郭（例外ハンドラ）に集約**し、`flownote.error.code` 付きで**1件だけ**記録する。これにより「中継ぎでログ → 上位でも catch してログ」という **log-and-rethrow**（同一事象の重複ログ）を防ぎ、`ERROR` ベースのアラートが歪まない。

- 認証/認可の失敗（401/403）は auth 層で監査/セキュリティログ済み（§別ストリーム）のため、境界では二重にログしない。
- 構造ガードレール: ドメイン層は可観測性に非依存、ドメイン/アプリ層はエラー段階ログを持たない（`apps/api/tests/observability/test_log_at_boundary.py` で固定）。

## 6. 相関とコンテキスト伝播

- **生成と束縛**: HTTP受信時にミドルウェアが span を開始し、`request_id`/`user.id`/`session_id` をコンテキスト（Python=`contextvars`、TS=`AsyncLocalStorage`）に束縛する。以降のログは自動でこれらを継承する。
- **境界越え**: サービス間/フロント↔バックは W3C `traceparent` ヘッダでトレース文脈を伝播する。
- **非同期**: バックグラウンドタスク/キューでも親 `trace_id` をリンク（OTel Link）して因果を保つ。
- 詳細トポロジは[可観測性アーキテクチャ](./observability-architecture.md)。

## 7. 環境別ログレベル

| 環境 | 既定レベル | トレース・サンプリング | プロンプト本文ログ |
|---|---|---|---|
| `local` | `DEBUG` | 100% | 既定オフ（明示有効化時のみ・マスク必須） |
| `dev` | `DEBUG` | 100% | オフ |
| `staging` | `INFO` | 20%（親決定ベース） | オフ |
| `prod` | `INFO` | 10%（+エラーは常時保持） | **禁止**（メタデータのみ） |

レベルは環境変数 `FLOWNOTE_LOG_LEVEL` で起動時に上書き可能。さらに**プロセス再起動なしに**実行時変更できる（本番事故時に再起動＝状態リセットを避けつつ一時的に `DEBUG` へ下げる等）:

- ライブラリ: `set_log_level(name)` / `get_log_level()`（閾値は重大度番号でプロセッサ段ゲートが適用）。
- API: `PUT /admin/log-level`（`ADMIN_MANAGE` 権限・変更は監査ログ `admin.log_level.change` に記録）。

## 8. サンプリング方針

- **トレース**: ヘッドベース（`ParentBased(TraceIdRatioBased)`）を既定とする。ローカルは100%。
- **エラー保持**: `ERROR` を含むトレースはサンプリング対象外にしない設計を推奨（Collector側 tail sampling を将来導入。ローカルでは全件保持）。
- **ログ**: レベルで一次制御。高頻度の `INFO`/`DEBUG` はイベント単位でレートリミット可（例: 同一 `body` を1秒N件まで）。**実装位置は structlog プロセッサ**（`build_processors` 内、重大度付与後・整形前にトークンバケットで間引く）に置く。
- **メトリクス**: 常時集計（サンプリングしない）。

### 8.1 パフォーマンス/コストの注意

- `code.lineno`/`code.function` の付与は**スタックフレーム検査**を伴い高頻度ログで重い。付けるなら**本番では `WARN` 以上に限定**する（DEBUG/INFO には付けない）。
- 重い属性（巨大オブジェクトのシリアライズ、ハッシュ計算）はホットパスで避け、必要時のみ算出する。

## 9. メトリクス規約（補足）

- **RED**: Rate（`http.server.request.count`）/ Errors（status>=500 比率）/ Duration（`http.server.request.duration` ヒストグラム）。
- **AI固有**: トークン使用量・レイテンシ・概算コスト（[GenAI可観測性](./genai-observability.md)）。
- メトリクス属性も本書のカーディナリティ規約に従う（高カーディナリティをラベルにしない）。

## 10. 禁止事項（アンチパターン）

- ❌ `print` / 素の `console.log` による出力（構造化されず相関しない）。
- ❌ メッセージ文字列への可変値埋め込み（集計不能）。
- ❌ 認証情報・PII・プロンプト全文の無制限ログ。
- ❌ ループ内の無制御 `INFO` ログ（コスト爆発）。
- ❌ 例外の握りつぶし（ログなしの `except: pass`）。
- ❌ **log-and-rethrow**（下位層でログ → 上位でも catch してログ。同一事象が重複し ERROR アラートが歪む）。エラーは§5.3の通り境界で1度だけ。
- ❌ クライアント応答へ内部詳細（SQL・内部ID・スタックトレース）を載せる（§5.1の分離を守る）。
- ❌ 可変メッセージ文字列でのエラー判別（§5.1の `flownote.error.code` を使う）。
- ❌ `trace_id` を持たないアプリログ（リクエスト文脈内なのに相関欠落）。

## 11. 準拠の固定（テスト）

本規約は文章ではなく**テストで固定**する（題材方針「テストこそ唯一の真実源泉」）。最低限、以下を `apps/api/tests/observability/` に置く:

- スキーマ準拠: 任意ログが `LogRecord` を満たし必須フィールドを持つ。
- 相関: リクエスト処理中のログに `trace_id`/`span_id` が入る。
- マスキング: 機密フィールドが出力でマスクされる（[マスキング規約](./redaction-policy.md)）。
- 重大度: 5xx/未捕捉例外が `ERROR`、4xxが `WARN`。
- 監査分離: 認証認可イベントが `event.domain` で分離される（[監査ログ](./audit-logging.md)）。
- エラー契約（§5）: ドメイン例外が安定 `code` と内部/外部分離を持つ（`tests/domain/test_errors.py`）。
- Problem Details（§5.2）: エラー応答が `application/problem+json` で `code`/`trace_id` を持ち、内部詳細を漏らさない（`tests/http/test_problem_details.py`）。
- 境界ログ（§5.3）: 失敗1件につき境界ログ1件。ドメイン/アプリ層はエラーログを持たない（`tests/observability/test_log_at_boundary.py`）。
