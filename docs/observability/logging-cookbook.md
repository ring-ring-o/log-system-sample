# ログ・クックブック（開発者DX） — 「やりたいこと → こう書く」

> 規約([logging-spec.md](./logging-spec.md))の全体像を覚えていなくても、**直感的に正しく**計装できるための最短レシピ集。迷ったら本書のスニペットをコピーし、規約の細部はライブラリ（`packages/observability-py` / `packages/observability-web`）に任せる。
>
> 原則: **アプリ開発者は OTel の属性名やマスキングを暗記しない。** 共有ファサードが規約を肩代わりする。直接 `print`/`console.log`/素のロガーを使わない。

## 0. まず覚える3つだけ

| やりたいこと | こう書く（Python） |
|---|---|
| 業務操作を計装（span＋業務ログ＋失敗時 span=ERROR） | `with operation("note.create") as op: op.set(**{"note.id": id})` |
| 単発の業務イベントを残す | `log_event("note.deleted", **{"note.id": id})` |
| クライアントにエラーを返す | `raise NotFoundError("note", id)`（境界が Problem Details＋ログ化） |

これ以外（アクセスログ・相関ID・トレース付与・マスキング）は**自動**。手で書かない。

## 1. 業務イベント／処理単位を計装したい

```python
from flownote_observability import operation, log_event

async def create_note(...) -> Note:
    note = Note(...)
    with operation("note.create") as op:      # span 開始（trace相関は自動）
        await repo.add(note)
        op.set(**{"note.id": note.id})         # 属性を足す（span＋ログ両方へ）
    return note                                # 正常終了で INFO ログを1件自動出力
```

- `operation(name)` の `name` は**低カーディナリティの固定名**（`note.create`）。可変値（ID）は `op.set(...)` で属性へ。
- 属性キーは**そのまま渡してよい**。`note_id=` → `flownote.note_id`、`{"note.id": ...}` → `flownote.note.id` のように `flownote.*` へ自動正規化（`http.*` 等の既知名前空間はそのまま尊重）。
- span だけ欲しい（ログ不要）なら `operation("x", emit=False)`。
- **例外が出たら**: span が自動で `ERROR` になり、例外は**そのまま再送出**される。ここでログは出さない（§3 参照）。

span を張るほどでもない単発イベントは `log_event("name", **attrs)` で十分。

## 2. HTTP アクセスログ・相関ID・trace_id

**何も書かない。** `ObservabilityMiddleware` が `request_id` 採番・`http.*` 属性・所要時間（秒）を自動記録し、全ログへ `trace_id`/`span_id` を相関付与する。`user.id`/`session_id` は認証時に自動束縛される。

> 手動で `bind_request_context(...)` を呼ぶのは新しい入口（バッチ/コンシューマ）を作るときだけ。

## 3. クライアントにエラーを返したい

ドメイン例外を **`raise` するだけ**。interface 層の境界が RFC 9457 Problem Details への変換と**1件だけ**のログ記録を行う（[logging-spec §5](./logging-spec.md)）。

```python
from flownote_api.domain.errors import NotFoundError, ValidationError

raise NotFoundError("note", note_id)        # → 404 + code=RES.NOT_FOUND
raise ValidationError("タイトルは空にできません")  # → 422 + code=VAL.INVALID
```

- **下位層で `try/except` してログしない**（log-and-rethrow 禁止）。失敗は投げるだけ。
- クライアントに見せてよい文言は `public_title`/`public_detail`、**ログにだけ出す機密**は `internal_context` に入れる:

```python
raise ConflictError("既に存在します", internal_context={"flownote.note.id": note_id})
```

- 新しいエラー種別は `domain/errors.py` に `code`/`http_status`/`public_title` を持つ `DomainError` サブクラスを足すだけ。`error_catalog()` に自動で載る。コードの命名規則・接頭辞は [logging-spec §5.1](./logging-spec.md)。
- **エラーコード一覧が欲しい**（フロント共有・サポート資料・棚卸し）→ 抽出コマンドを使う。手で表を書かない:

```bash
uv run --package flownote-api flownote-error-catalog                 # Markdown 表（ドメイン＋境界の全コード）
uv run --package flownote-api flownote-error-catalog --format json   # JSON（フロント共有）
uv run --package flownote-api flownote-error-catalog --format csv    # CSV
```

生成物は [error-catalog.md](./error-catalog.md)。CI はコード追加時の追従漏れを `--check` で弾く（[apps/api README](../../apps/api/README.md)）。

## 4. AI 呼び出しを計装したい

`GenAIInstrumentation.call(...)` の `with` ブロックで使用量・応答を記録するだけ。`gen_ai.*` 属性・トークン/レイテンシ/コスト計測・本文マスキングは自動（[genai-observability.md](./genai-observability.md)）。

```python
with genai.call(operation="chat", system="openai", request_model=model, use_case="task_consult") as call:
    resp = await client.chat(...)
    call.record_usage(input_tokens=resp.usage.input, output_tokens=resp.usage.output)
```

## 5. 認証・認可・セキュリティを記録したい

`emit_audit(...)` / `emit_security(...)` を使う。`event.domain=audit/security` で業務ログと別ストリームになり、成功=INFO・失敗/拒否=WARN を自動判定（[audit-logging.md](./audit-logging.md)）。

## 6. 機密はどう扱う？

- **基本は気にしなくてよい。** マスキングプロセッサがキー名（`password`/`token`/`authorization` 等）と値パターン（JWT/Bearer/APIキー/メール）を最終安全網として除去する。
- ただし**安全網に頼り切らない**: 生のパスワード/トークン/プロンプト全文を属性に**入れない**。識別子はハッシュ化する（`*.query_hash`、`session_id` は自動ハッシュ）。

## 7. フロントエンド（TS）

`packages/observability-web` の `ClientLogger` と計装済み `fetch` を使う。`traceparent` 付与・`http.client.*`（所要時間は秒）・送出前マスキングは自動（[frontend-logging.md](./frontend-logging.md)）。`console.log` 直出力は禁止。

- **API エラーはコードで分岐**: `shared/api-client.ts` が Problem Details を解析し `ApiError`（`code`/`title`/`detail`/`traceId`）を投げる。`if (e instanceof ApiError && e.code === "VAL.REQUEST")` のように**安定コードで分岐**する（メッセージ文字列に依存しない）。エラーは `flownote.error.code` 付きで自動ログされる。
- **コード集合は手書きしない**: `pnpm --filter web gen:errors` でバックエンド SSOT から `error-catalog.generated.ts`（`ErrorCode` 型）を生成・参照する（[frontend-logging §3.1](./frontend-logging.md)）。

## やってはいけない（DX以前の禁止事項）

- ❌ `print` / 素の `console.log`。→ `operation`/`log_event`/`ClientLogger`。
- ❌ メッセージに値を埋め込む（`f"note {id} created"`）。→ 固定名＋属性。
- ❌ 下位層でのエラーログ（log-and-rethrow）。→ `raise` だけ。ログは境界。
- ❌ クライアント応答へ内部詳細を載せる。→ `internal_context` はログのみ。
- ❌ 可変メッセージでエラー判別。→ `code`（`flownote.error.code`）で分岐。

詳細規約は [logging-spec.md](./logging-spec.md)、設計判断は [observability-architecture.md](./observability-architecture.md)。
