---
name: design-tokens
description: >-
  デザイントークン(色/タイポグラフィ/スペーシング/角丸/影/モーション/zインデックス)を
  体系的に定義・命名・実装するためのスキル。新規UIの基盤を作る、トークンを追加/改名する、
  CSS変数やTSの型付きトークンを整備する際に使用する。
---

# デザイントークン スキル

UIの見た目を**ハードコードせず**、意味のある名前(token)で一元管理するための規約。色や余白を直接書かず、トークンを参照する。

## 階層: 3層モデル

1. **Primitive(原始トークン)**: 生の値。意味を持たない。`color.blue.500 = #3b82f6`, `space.4 = 16px`。
2. **Semantic(意味トークン)**: 用途で命名。primitiveを参照。`color.bg.default`, `color.text.muted`, `color.border.focus`。**UIはここを参照する**。
3. **Component(任意)**: 特定部品向け。semanticを参照。`button.primary.bg`。

UI実装は**semantic層のみ**を参照する（primitiveの直接参照を禁止）。これでテーマ変更（ダークモード等）が中央で完結する。

## 命名規約

- ドット区切りの階層: `<category>.<role>.<variant?>.<state?>`。
  - 例: `color.text.default`, `color.bg.subtle`, `color.intent.danger.fg`, `space.4`, `radius.md`, `shadow.sm`, `font.size.body`, `font.weight.bold`, `z.modal`。
- 状態は接尾辞: `.hover` / `.active` / `.disabled` / `.focus`。
- 真偽/モードは別ファイルかセレクタ(`[data-theme=dark]`)で上書きし、トークン名は変えない。

## カテゴリ（最低限揃える）

| カテゴリ | 例 |
|---|---|
| color | bg/text/border/intent(primary,success,warning,danger,info) |
| space | 0,1,2,3,4,6,8,12,16... (4pxグリッド) |
| font | family, size(xs..2xl), weight, lineHeight |
| radius | none,sm,md,lg,full |
| shadow | sm,md,lg |
| z | base,dropdown,sticky,modal,toast |
| motion | duration(fast/base/slow), easing |

## 実装方式

- **単一の源**: `tokens.json`(またはTS)に定義 → CSS変数(`:root { --color-bg-default: ... }`)とTSの型付き定数を生成/手書き。
- CSS変数で実体を持ち、TS側は**型付きキー**でアクセス（補完と検査が効く）。
- ダーク/ライトは `[data-theme]` でCSS変数を上書き。トークン参照側は無変更。
- アクセシビリティ: テキスト/背景のコントラスト比 WCAG AA(4.5:1)以上を意図して semantic を設計。

## やってはいけない

- コンポーネントに生の色/px直書き（`#fff`, `12px`）。必ずトークン参照。
- primitive層をUIから直接参照（テーマ変更が破綻）。
- 状態違いを別トークン名で乱立（状態接尾辞で表現）。

## レビュー観点（`code-review-standards` と併用）

- [ ] 生値の直書きがないか。
- [ ] semantic層を参照しているか。
- [ ] 新規トークンが命名規約に従うか。
- [ ] ダークモードでも破綻しないか（semantic経由か）。

## 本リポジトリでの所在

`apps/web` 配下のトークン定義（CSS変数＋TS型）。フロントのUIプリミティブはトークンのみを参照する。
