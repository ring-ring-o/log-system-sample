# ADR 0004: 認証認可に Keycloak (OIDC) + ロールベース認可を採用する

- ステータス: 採用
- 日付: 2026-05-31

## 背景

要件は OAuth2 / OIDC、Keycloak、ロールベース認可(RBAC)。認証認可は[監査ログ](../observability/audit-logging.md)観察の主要対象でもある。

## 決定

- **IdP**: Keycloak（OIDCプロバイダ）。realm/クライアント/ロールを realm import で定義。
- **フロント**: Auth.js(NextAuth v5) の Keycloak プロバイダでログイン、アクセストークンをAPIへ伝播。
- **バックエンド**: 受領したJWTを **JWKS** で検証（署名・`exp`・`aud`・`iss`）。トークン内のロールで**RBAC**を実施。
- **認可の所在**: アプリ層(`interface/security/`)で判定し、判定結果（特に拒否）を必ず監査ログ化。ドメイン層は権限を意識しない。

## ロール

`viewer` / `editor` / `admin`（[監査ログ §4](../observability/audit-logging.md)）。

## 理由

- 標準プロトコル(OIDC)準拠でロックインを避ける。
- Keycloak はローカルで動くOSSで要件に合致。
- 認証認可イベントを監査/セキュリティログとして観察する教材価値が高い。

## 留意

- 開発を止めないため、Keycloak未起動でもテストが回るよう、JWT検証アダプタは Protocol 化し、テストではフェイク（既知の公開鍵/クレーム）で差し替える。
- トークン・client_secret は[マスキング規約](../observability/redaction-policy.md)で必ず秘匿。

## 代替案

- 自前JWT発行 → 標準・教材価値・委譲の観点で劣る。却下。
