---
name: observability-logging
description: >-
  OpenTelemetry準拠の構造化ログ/トレース/メトリクス設計を実装・レビューするための再利用スキル。
  Webサービス(バックエンド/フロント/AI/認証)に可観測性を導入する、既存ログを規約準拠にする、
  ログの相関・マスキング・サンプリング・GenAI/監査ログを設計する際に使用する。
---

# 共通ログ設計スキル（OpenTelemetryベース）

任意のプロジェクトに「3本柱(ログ/トレース/メトリクス)を相関させた可観測性」を最短で導入するためのテンプレートと判断基準。本リポジトリの規約原典は `docs/observability/`。

## 使うべき場面

- 新規Webサービスにログ/可観測性を入れる。
- 既存の `print`/素のloggerを構造化ログ＋相関に移行する。
- AI呼び出し・認証認可のログを設計する。
- ログ実装をレビューする（`code-review-standards` と併用）。

## 中核の意思決定（最初に決める6つ）

1. **規格**: OpenTelemetry を採用（ベンダ非依存）。収集先(SigNoz/Grafana/Datadog)は OTLP の先で差し替え可能にする。
2. **形式**: 構造化JSON（1イベント1行）。整形は閲覧側の責務。
3. **相関キー**: `trace_id`/`span_id` を全アプリログに付与。加えて `request_id`/`session_id`/`user.id`。
4. **重大度**: TRACE/DEBUG/INFO/WARN/ERROR/FATAL の6段＋OTel severity number。4xx=WARN、5xx/未捕捉=ERROR。
5. **属性命名**: OTel Semantic Conventions(`http.*`/`db.*`/`gen_ai.*`/`exception.*`)。独自は `<app>.*` 名前空間。
6. **マスキング**: ロガーのプロセッサで機密キー/パターンを必ず除去（最後の安全網）。

## ログレコード最小スキーマ

```
timestamp(RFC3339 nano) / severity_text / severity_number /
body(低カーディナリティのイベント名) / service.name / service.version /
deployment.environment / trace_id / span_id / attributes{...}
```

- `body` に可変値を埋め込まない（×`f"user {id}..."`）。固定名＋属性で集計可能に。
- 高カーディナリティ値(ID等)は属性へ。route はテンプレート(`/notes/{id}`)。

## レイヤ別の要点

| レイヤ | やること |
|---|---|
| 共有ライブラリ | OTel初期化・structlog(or 同等)プロセッサ・コンテキスト束縛・マスキング・GenAI計測をここに集約。アプリはここだけに依存。 |
| HTTPミドルウェア | span開始 → `request_id`/`user`をコンテキスト束縛 → アクセスログ + RED計測。 |
| ドメイン/UC境界 | 業務的に意味のある単位で手動span。例外は型で分類し ERROR+`exception.*`。 |
| AI呼び出し | `gen_ai.*` 属性付きspan。token/latency/コスト計測。プロンプト本文は既定オフ＋マスク＋トランケート。 |
| 認証認可 | `event.domain=audit/security` で業務ログと分離。拒否は必ず記録。 |
| フロント | ブラウザSDKでfetchにtraceparent付与。クライアントエラー/Web Vitalsを収集、送出前にマスク。 |

## コンテキスト伝播

- Python: `contextvars`。TS: `AsyncLocalStorage`。
- 境界越え: W3C `traceparent` ヘッダ。
- 非同期/キュー: 親trace_idをOTel Linkで関連付け。

## サンプリング/コスト

- トレース: `ParentBased(TraceIdRatioBased)`。local=100%、prodは10%目安、ERRORは常時保持。
- ログ: レベルで一次制御。高頻度INFO/DEBUGはレートリミット。
- メトリクス: 常時集計（サンプリングしない）。

## 必ずテストで固定する（規約=テスト）

- スキーマ準拠（必須フィールド）/ 相関(trace_id付与) / マスキング / 重大度(5xx=ERROR) / 監査分離 / GenAI必須属性。

## エラー設計（ログと表裏一体）

- **安定エラーコード**: 例外に `<DOMAIN>.<NAME>`(例 `RES.NOT_FOUND`)を持たせ、ログに `flownote.error.code`、応答に `code` として出す。クラス名やメッセージで判別させない。
- **内部/外部分離**: 例外は `public_title`/`public_detail`(公開)と `internal_context`(ログ専用・機密含む)を構造的に分ける。応答に内部詳細を載せない。
- **RFC 9457 Problem Details**: クライアント応答は `application/problem+json`(`type`/`title`/`status`/`code`/`detail`/`instance`/`trace_id`)に統一。`trace_id` でサポートが引き戻せる。
- **境界で1度だけログる**: 下位層は `raise` のみ。ログは interface 層の例外ハンドラに集約し1件だけ記録(log-and-rethrow 禁止)。認証認可失敗は監査/セキュリティで別途記録済みなので二重ログしない。

## アンチパターン

`print`直出力 / メッセージへの値埋め込み / 機密の無制限ログ / ループ内無制御INFO / 例外握りつぶし / **log-and-rethrow(重複ログ)** / **応答への内部詳細漏洩** / **可変メッセージでのエラー判別** / trace_idなしアプリログ。

## 参照

実装の詳細規約: `docs/observability/logging-spec.md` ほか同ディレクトリ。
