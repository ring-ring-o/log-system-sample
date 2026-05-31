# 監査ログ（Audit & Security Logging）

> 認証・認可・機微操作の**監査ログ**規約。業務ログ(`event.domain=app`)とは**分離**して扱う。
> 基本規約は[ログ規約(SSOT)](./logging-spec.md)。

## 1. なぜ分離するか

監査ログは「誰が・いつ・何に・成功/失敗したか」を**説明責任(accountability)**のために残す。業務ログとは保持期間・改竄耐性・アクセス制御・サンプリング方針が異なるため、`event.domain` で明確に区別し、収集経路でも別ストリーム化できるようにする。

| 分類(`event.domain`) | 目的 | サンプリング | 例 |
|---|---|---|---|
| `audit` | 認証認可・権限変更・機微操作の証跡 | **しない（全件）** | ログイン、ロール判定、認可拒否、削除操作 |
| `security` | 攻撃・異常の検知 | しない | トークン検証失敗、ブルートフォース兆候、CSRF/CORS違反 |
| `access` | HTTPアクセスログ | レベル/レート制御可 | リクエスト完了 |
| `app` | 業務イベント | レベル制御 | メモ作成成功 |

## 2. 監査イベント・スキーマ

監査ログは[ログ規約](./logging-spec.md)のスキーマに加え、`attributes` に以下を持つ。Pydanticモデル `AuditEvent` で固定する。

| 属性 | 必須 | 説明 |
|---|---|---|
| `event.domain` | ✅ | `audit` / `security` |
| `audit.action` | ✅ | 動詞.対象（`auth.login`, `auth.logout`, `authz.decision`, `note.delete`, `role.assign`） |
| `audit.outcome` | ✅ | `success` / `failure` / `denied` |
| `user.id` | 条件付 | 主体（Keycloak `sub`）。未認証なら null＋ `security` |
| `user.roles` | 任意 | 判定時点のロール |
| `authz.resource` | authz時 | 対象リソース（`note:{id}` 等） |
| `authz.permission` | authz時 | 要求権限（`note:read` 等） |
| `authz.decision` | authz時 | `allow` / `deny` |
| `client.address` | ✅ | 送信元IP（[マスキング](./redaction-policy.md)方針に従い必要なら丸め） |
| `network.protocol` / `user_agent.original` | 任意 | 補助情報 |
| `request_id` / `trace_id` | ✅ | 相関 |

**機密の非格納**: パスワード・トークン・コードなどは絶対に格納しない。`user.id` は不透明ID、メール等PIIは入れない（§[マスキング](./redaction-policy.md)）。

## 3. 必ず監査する操作

- **認証**: ログイン成功/失敗、ログアウト、トークン更新失敗、トークン検証失敗（`security`）。
- **認可**: ロールベース判定の**拒否(denied)** は必ず記録。許可(allow)は機微リソースのみ記録（量制御）。
- **権限/ロール変更**: 付与・剥奪。
- **機微データ操作**: 削除（メモ/タスク/バージョン）、エクスポート、他者リソースへのアクセス。

## 4. 認可モデル（RBAC）との対応

Keycloak のロールを用いたロールベース認可。代表ロール:

| ロール | 権限の概略 |
|---|---|
| `viewer` | 自身のメモ/タスクの閲覧・検索 |
| `editor` | viewer + 作成・更新・バージョン作成・AI相談 |
| `admin` | editor + 削除・他ユーザー管理・監査閲覧 |

認可判定（`authz.decision`）は**必ず1イベントとして監査**し、`denied` は `WARN`、許可は `INFO`。判定はアプリ層（`apps/api/.../interface/security/`）で行い、ドメイン層は権限を意識しない（関心の分離）。

## 5. 改竄耐性・保持

- 監査ログは**追記専用**として扱い、アプリ内で更新・削除しない。
- 収集先（SigNoz/将来は専用ストア）で保持期間を業務ログより長く設定（例: 業務30日 / 監査365日）。本リポジトリでは方針の明記に留める（ローカル前提）。
- 改竄検知が要件化した場合はハッシュチェーン/署名を将来導入（ADR化）。

## 6. セキュリティログ（`security`）

- トークン検証失敗（署名不正・期限切れ・aud不一致）。
- 短時間の連続失敗（ブルートフォース兆候）→ `WARN`、閾値超で `ERROR`。
- CORS/CSRF 違反、想定外オリジン。
- これらは個人特定よりも**攻撃検知**が目的。`user.id` 不明でも `client.address` 等で記録。

## 7. テストで固定する事項

- ログイン成功/失敗が `audit.action=auth.login` + `audit.outcome` で記録される。
- 認可拒否が `event.domain=audit`, `authz.decision=deny`, `severity=WARN` で記録される。
- トークン検証失敗が `event.domain=security` で記録される。
- 監査ログに機密（パスワード/トークン）が含まれない（[マスキング](./redaction-policy.md)テストと連携）。
- 監査ログが業務ログと `event.domain` で判別可能。
