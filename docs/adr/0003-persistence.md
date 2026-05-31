# ADR 0003: 永続化に PostgreSQL + SQLAlchemy 2.0(async) + Alembic を採用する

- ステータス: 採用
- 日付: 2026-05-31

## 背景

要件で DB は PostgreSQL 指定。バックエンドは Python 3.14 / FastAPI(async)。契約と境界を守りつつ、自動計装で db span を取得したい。

## 決定

- DB: **PostgreSQL**。
- ORM/クエリ: **SQLAlchemy 2.0** の async API + **asyncpg** ドライバ。
- マイグレーション: **Alembic**。
- リポジトリは `domain/ports.py` の Protocol を実装する `infrastructure/db/` のアダプタとして提供。ドメインモデルとORMモデルは分離し、境界で変換する。

## 理由

- SQLAlchemy は OTel 自動計装があり、`db.*` 属性付きの span を低コストで取得できる（[アーキテクチャ §7](../observability/observability-architecture.md)）。
- async でFastAPIと整合。
- ドメインを ORM から独立させ、テスト（インメモリ実装）を高速化（[architecture.md §6](../architecture.md)）。

## 代替案

- SQLModel → ドメインとORM/DTOが密結合になりやすく、境界分離の方針に反する。却下。
- 生SQL(asyncpg直) → 計装と保守の利点が薄い。却下。

## 影響

- 依存追加: `sqlalchemy`, `asyncpg`, `alembic`。最小限に留める。
- テストはインメモリ・リポジトリ実装で contract テストを満たす設計とする。
