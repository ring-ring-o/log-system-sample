# packages/observability-py — 共有可観測性ライブラリ（Python）

`flownote-observability`。**ログ／トレース／メトリクスを OpenTelemetry 準拠で扱うための中核パッケージ**。
バックエンド（[apps/api](../../apps/api/README.md) 等）はこのパッケージ**のみ**を経由してログを扱い、特定ベンダに固定されない。

> 本プロジェクトの真の成果物（可観測性システム）の実装本体。規約は
> [ログ規約(SSOT)](../../docs/observability/logging-spec.md) を一次資料とし、本パッケージはそれをコードで具現化する。

## 公開 API（[`__init__.py`](./src/flownote_observability/__init__.py)）

| 入口 | 役割 |
|---|---|
| `operation(name, **attrs)` | **高レベルファサード**。span＋業務ログ＋失敗時 span=ERROR を1行で（→[クックブック](../../docs/observability/logging-cookbook.md)） |
| `log_event(name, **attrs)` | span 不要の単発業務イベントを INFO で記録（名前空間・`event.domain` を自動付与） |
| `bootstrap(config)` | ログ + トレース/メトリクスを一括初期化（合成ルートで一度だけ呼ぶ） |
| `get_logger(name)` | 構造化ロガーを取得（低レベル。通常は `operation`/`log_event` を使う） |
| `GenAIInstrumentation` / `GenAICall` | AI 呼び出しの計装（トークン・モデル・レイテンシ） |
| `emit_audit` / `emit_security` | 監査／セキュリティログの記録（`AuditOutcome` / `AuthzDecision`） |
| `bind_request_context` / `clear_request_context` / `hash_session_id` | 相関コンテキストの束縛・解除・セッション ID ハッシュ |
| `Severity` / `severity_for_http_status` / `severity_from_name` | 重大度の正規化 |
| `configure_logging` / `configure_otel` | 個別初期化（`bootstrap` の構成要素） |
| `get_tracer` / `get_meter` | OTel トレーサ／メータの取得 |
| `ObservabilityConfig` / `LogRecord` | 構成・ログレコードスキーマ |

## モジュール構成（[`src/flownote_observability/`](./src/flownote_observability/)）

```
operations.py     高レベルファサード（operation/log_event。開発者DXの入口）
config.py         ObservabilityConfig（環境変数からの構成・from_env）
logging_setup.py  structlog ベースの構造化ログパイプライン
otel.py           OTel トレース/メトリクスの設定（OTLP/HTTP・console/file フォールバック）
context.py        相関コンテキスト（trace_id/span_id・request/session の束縛）
schema.py         LogRecord（共通ログスキーマ）
severity.py       重大度（OTel SeverityNumber との対応）
redaction.py      マスキング（秘匿フィールドの削除/ハッシュ化）
genai.py          GenAI 計装（AI 呼び出しのトークン/モデル計測）
audit.py          監査/セキュリティログ（分離・改ざん耐性を意識した記録）
```

関連規約: [redaction-policy.md](../../docs/observability/redaction-policy.md) /
[genai-observability.md](../../docs/observability/genai-observability.md) /
[audit-logging.md](../../docs/observability/audit-logging.md) /
[observability-architecture.md](../../docs/observability/observability-architecture.md)。

## コマンド（リポジトリルートから / Python 3.14・uv）

```bash
uv sync                                   # 依存解決(uv ワークスペース)
uv run ruff format . && uv run ruff check --fix .   # フォーマット+リント
uv run mypy                               # 型チェック(strict)
uv run pytest packages/observability-py   # テスト
```

## テスト（規約をコードで固定する）

[`tests/`](./tests/) で可観測性規約を固定する。ログパイプライン・マスキング・重大度・GenAI 計装・監査/相関を網羅し、
仕様変更はまずテストで契約を書く（[architecture.md §6](../../docs/architecture.md)）。

## 設計メモ

- 依存は `structlog` + `opentelemetry-*`（API/SDK/OTLP-HTTP exporter）+ `pydantic`。**ベンダ非依存**。
- ログは標準出力（JSON）、トレース/メトリクスは OTLP。収集先未起動時は console/file exporter で観察を担保する。
- ブラウザ側の対になるパッケージは [observability-web](../observability-web/README.md)（スキーマ・重大度を揃える）。
