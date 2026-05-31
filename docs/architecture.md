# アーキテクチャ（System Architecture）

> モノレポ構成・レイヤリング・契約と境界の方針。可観測性は[こちら](./observability/observability-architecture.md)、コンセプトは[こちら](./concept.md)。

## 1. 設計原則

1. **契約と境界(Contracts & Boundaries)**: モジュール間はインターフェース（Python `typing.Protocol` / ABC、TS `interface`）と**ドメインモデル**で結合する。境界の入出力は **Pydantic / Zod** で検証する。
2. **一方向の依存(Onion/Layered)**: 依存は外側→内側の一方向のみ。**ドメインは何にも依存しない**。
3. **テストが唯一の真実源泉(SSOT)**: 詳細設計書は作らない。**契約と境界の定義はテスト**で固定する。ドメインに紐づくテストを正とする。
4. **宣言的**: 命令的手続きより、型・データ・不変条件で意図を表す。
5. **依存は最小限**: ライブラリ追加は慎重に。標準機能とOTel/Pydantic/SQLAlchemy等の中核に限定。

## 2. モノレポ構成

```
flownote/
├─ apps/
│  ├─ api/          # FastAPI バックエンド（レイヤード）
│  ├─ web/          # Next.js 16 フロントエンド
│  └─ ai-mock/      # OpenAI互換モックサーバ（開発用）
├─ packages/
│  ├─ observability-py/   # 共有: 構造化ログ/OTel/相関/マスキング/GenAI計測（中核）
│  └─ observability-web/  # 共有: ブラウザ計装/クライアントロガー
├─ infra/           # docker-compose, otel-collector, keycloak realm, signoz
├─ docs/            # 設計・規約（本ディレクトリ）
├─ .claude/skills/  # 再利用スキル
├─ pyproject.toml         # uv workspace ルート
├─ pnpm-workspace.yaml    # pnpm workspace ルート
└─ CLAUDE.md
```

- **Python側**: uv workspace（メンバ: `apps/api`, `apps/ai-mock`, `packages/observability-py`）。
- **TS側**: pnpm workspace（メンバ: `apps/web`, `packages/observability-web`）。
- 言語をまたぐ共有はソース共有ではなく**規約([ログ規約](./observability/logging-spec.md))とOTLPプロトコル**で揃える。

## 3. バックエンドのレイヤリング（`apps/api`）

依存方向: `interface → application → domain`、`infrastructure → (application, domain)`。**domain は外向き依存ゼロ**。

```
flownote_api/
├─ domain/          # 内核: 依存ゼロ
│  ├─ notes/        # Note エンティティ・値オブジェクト・不変条件
│  ├─ tasks/        # Task, TaskStatus
│  ├─ versions/     # Version, Diff
│  ├─ ai/           # AI関連の値オブジェクト・ユースケース型
│  ├─ identity/     # User, Role, 認可ポリシ（純粋ロジック）
│  ├─ ports.py      # リポジトリ/AI/時計などの Protocol（契約）
│  └─ errors.py     # ドメイン例外
├─ application/     # ユースケース（ports に依存、実装は知らない）
│  └─ usecases/     # CreateNote, SearchUnified, ConsultTask ...
├─ infrastructure/  # アダプタ（ports を実装）
│  ├─ db/           # SQLAlchemy 2.0(async) リポジトリ, models, alembic
│  ├─ ai/           # OpenAI互換クライアント（GenAI計装）
│  ├─ security/     # Keycloak JWKS 検証
│  └─ observability/# OTel/ログ ブートストラップ（observability-py を使用）
├─ interface/       # 外界との境界
│  ├─ http/         # FastAPI ルータ・Pydanticスキーマ（DTO）
│  ├─ middleware/   # ログ/トレース、request_id、例外→HTTP変換
│  └─ security/     # 認可（RBAC）ガード, 監査ログ発火
└─ main.py          # 合成ルート(Composition Root): DIで束ねる
```

### 契約の所在

- **`domain/ports.py`** が契約の中心。例:
  - `NoteRepository(Protocol)`, `TaskRepository`, `VersionRepository`
  - `AIAssistant(Protocol)`（`consult`, `search`, `review_progress`）
  - `Clock`, `IdGenerator`
- `application` はこれら Protocol にのみ依存。`infrastructure` が実装を提供し、`main.py` で注入する。
- **境界DTO**は Pydantic（`interface/http/schemas`）。ドメインモデルは Pydantic ではなく純粋な dataclass/値オブジェクトとし、DTO↔ドメインの変換を明示する（ドメインをフレームワークから守る）。

## 4. フロントエンドの構成（`apps/web`）

- Next.js 16 App Router。`features/`（notes/tasks/versions/ai/auth）単位でUI・hook・APIクライアントを凝集。
- `shared/` に API クライアント（traceparent伝播）、`observability-web` 初期化、UIプリミティブ（[デザイントークン](../.claude/skills/design-tokens/SKILL.md)準拠）。
- 認証は Auth.js(Keycloak OIDC)。RBACでUI出し分け、APIアクセスはトークン付与。

## 5. データモデル（概略）

- `User`(Keycloakが主、アプリはsub参照) / `Note`(id, owner, title, body, created/updated) / `Version`(id, note_id, body, parent_id, created_at) / `Task`(id, owner, note_id?, title, status, created/updated)。
- バージョンは**追記専用**（メモ更新時に新バージョン生成）。
- 詳細スキーマは Alembic マイグレーション＋テストで固定（設計書化しない）。

## 6. テスト戦略（SSOT）

| レベル | 対象 | 置き場所 |
|---|---|---|
| ドメイン単体 | 不変条件・値オブジェクト・認可ポリシ | `tests/domain/` |
| ユースケース | application（ports はフェイク実装で差し替え） | `tests/application/` |
| 契約 | infrastructure アダプタが Protocol を満たす | `tests/contracts/` |
| 可観測性 | ログ/相関/マスキング/監査（[規約](./observability/logging-spec.md)の固定） | `tests/observability/` |
| インターフェース | FastAPI エンドポイント（httpx + ASGI） | `tests/http/` |

- フェイク/インメモリ実装でユースケースを高速にテストし、DBは契約テストとマイグレーションで担保。
- 「テスト＝仕様」。新機能は**まずテストで契約を書く**。

## 7. 合成ルート（DI）

- `main.py` が唯一、具体実装を選んで注入する（環境で差し替え: 本物DB/AI vs フェイク/モック）。
- これにより `local` ではAIモック・SQLite/Postgres、テストではインメモリ、と切替が宣言的になる。

## 8. 技術選定（ADR）

主要判断は `docs/adr/` に記録: [OTel採用](./adr/0001-opentelemetry.md) / [SigNoz](./adr/0002-signoz.md) / [永続化(SQLAlchemy)](./adr/0003-persistence.md) / [認証(Keycloak)](./adr/0004-auth-keycloak.md)。
