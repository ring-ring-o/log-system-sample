# エラーコードカタログ（自動生成）

> このファイルは `flownote-error-catalog` が生成する。**手で編集しない**。
> 再生成 / 差分チェックは [apps/api README](../../apps/api/README.md) を参照。

| コード | HTTP | origin | タイトル | 公開詳細 | 発行元 |
|---|---|---|---|---|---|
| AUTH.UNAUTHORIZED | 401 | interface | 認証が必要です | 有効な認証情報が必要です | flownote_api.infrastructure.security.token.InvalidTokenError |
| AUTHZ.DENIED | 403 | domain | 権限がありません | — | flownote_api.domain.errors.PermissionDeniedError |
| GEN.INTERNAL | 500 | domain | 内部エラーが発生しました | — | flownote_api.domain.errors.DomainError |
| RES.CONFLICT | 409 | domain | リソースが競合しています | — | flownote_api.domain.errors.ConflictError |
| RES.NOT_FOUND | 404 | domain | リソースが見つかりません | — | flownote_api.domain.errors.NotFoundError |
| VAL.INVALID | 422 | domain | 入力が不正です | — | flownote_api.domain.errors.ValidationError |
| VAL.REQUEST | 422 | interface | 入力が不正です | リクエストの内容を確認してください | fastapi.exceptions.RequestValidationError |
