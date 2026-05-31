# マスキング規約（Redaction / PII Policy）

> ログ・トレース・メトリクスに**機密情報を出さない**ための規約。全シグナルに適用。
> 基本規約は[ログ規約(SSOT)](./logging-spec.md)。

## 1. 原則

1. **最小収集**: そもそも機密を属性に入れない設計を最優先。マスキングは最後の安全網。
2. **多層防御**: ①開発者が入れない → ②ロガーのプロセッサで自動マスク → ③Collector でも除去可能、の多層で守る。
3. **不可逆**: マスク値は復元不可能にする（`***` 置換 or 一方向ハッシュ）。
4. **テストで固定**: マスキングはテストで保証する（§5）。

## 2. 機密の分類と扱い

| 分類 | 例 | 扱い |
|---|---|---|
| 認証情報(secrets) | パスワード、`Authorization` ヘッダ、Bearerトークン、APIキー、Cookie、`client_secret` | **完全削除**（キーごと除去 or `***`） |
| 直接PII | メールアドレス、氏名、電話番号 | 既定マスク（`u***@***`）。`user.id`(不透明ID)で代替 |
| 準PII | IPアドレス、`User-Agent` 詳細 | 必要時のみ。IPは監査で保持可、それ以外は丸め/省略 |
| ユーザー生成内容 | メモ本文、プロンプト、検索クエリ | 既定で本文を出さない。必要時はハッシュ/トランケート（[GenAI](./genai-observability.md)） |

## 3. マスキング方式

### 3.1 フィールド名ベース（キー一致）

以下のキー（大小無視・部分一致）は値を `***` に置換、または除去:

```
password, passwd, secret, token, access_token, refresh_token, id_token,
authorization, api_key, apikey, client_secret, cookie, set-cookie,
private_key, credential, session, otp
```

### 3.2 値パターンベース（正規表現）

キー名に依らず、値が以下にマッチしたら該当部分をマスク:

- JWT: `eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+` → `***JWT***`
- Bearer: `(?i)bearer\s+[A-Za-z0-9._-]+` → `Bearer ***`
- メール: `[\w.+-]+@[\w-]+\.[\w.-]+` → `***@***`（PII方針に従い）
- 代表的APIキー形（`sk-...` 等）→ `***`

### 3.3 ユーザー識別子

- `user.id` は Keycloak `sub`（不透明UUID）。**メールや表示名はログに出さない**。
- `session_id` はそのまま出さず **SHA-256 の先頭16桁** 等に短縮ハッシュ化（突合は可能、値は秘匿）。

## 4. 実装

- 単一の実装 `packages/observability-py/.../redaction.py::redact(value)` を全ロガー（structlog プロセッサ）に挿入する。トレース属性・GenAIヘルパもこの関数を経由。
- フロントは `packages/observability-web` のロガー送出前に同等のキー/パターンマスクを適用。
- マスク対象リスト・正規表現は**設定ではなくコードで一元管理**し、テストで固定する（規約=テスト）。
- 既定では再帰的に dict/list を走査してマスク。深さ・サイズ上限を設けDoSを防ぐ。

## 5. テストで固定する事項（`tests/observability/test_redaction.py`）

- `Authorization`/`password`/`token`/`cookie` キーが出力で `***` になる。
- 値に埋め込まれた JWT/Bearer がマスクされる。
- メールがマスク（または `user.id` 置換）される。
- ネストした dict/list 内の機密もマスクされる。
- マスク後にスキーマ([ログ規約](./logging-spec.md))が壊れない（必須フィールドは保持）。
- パフォーマンス: 想定サイズで過大な遅延がない（深さ/サイズ上限の確認）。

## 6. 運用上の注意

- 例外メッセージ・スタックトレースにも機密が混入しうる → `exception.message` にもマスクを適用。
- 新しい機密フィールドを追加した機能では、必ずマスク対象リストとテストを更新する（レビュー基準: [code-review-standards スキル]）。
