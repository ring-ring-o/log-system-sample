---
name: git-workflow
description: >-
  機能単位コミット・固定プレフィックス(add/update/fix/delete)・GitHub flow・適切な.gitignoreを
  徹底するためのgit運用スキル。コミットメッセージを書く、ブランチを切る、変更を統合する、
  .gitignoreを整える際に使用する。
---

# git運用スキル（機能単位 / 固定プレフィックス / GitHub flow）

## コミット規約

### プレフィックス（固定4種のみ）

| prefix | 用途 |
|---|---|
| `add` | 新規ファイル・新機能・新規追加 |
| `update` | 既存の変更・改善・リファクタ |
| `fix` | バグ修正・誤りの是正 |
| `delete` | 削除・除去 |

メッセージ書式:
```
<prefix>: 日本語の要約(50文字目安・命令形/体言止め)

本文(任意): なぜ変更したか・補足。72文字目安で折り返し。

Co-Authored-By: ...
```

### 粒度: 機能単位

- 1コミット=1つの意味のある変更（機能/修正）。無関係な変更を混ぜない。
- 「動く」状態でコミットする（テストやビルドが通る単位）。
- フォーマットのみの変更は機能変更と分け、`update` で単独コミット。

## ブランチ戦略: GitHub flow

1. `main` は常にデプロイ可能。
2. 作業は `main` から機能ブランチを切る: `feat/<topic>` / `fix/<topic>`。
3. 小さく頻繁にコミット。
4. 完了したら `main` へ統合（PRが基本。ローカル完結時は `--no-ff` マージで履歴を残す）。
5. 統合後はブランチ削除。

```bash
git checkout -b feat/<topic>
# ... add/update/fix/delete コミット ...
git checkout main
git merge --no-ff feat/<topic> -m "Merge feat/<topic>"
git branch -d feat/<topic>
```

- push はユーザーが明示したときのみ。リモート未設定なら勝手に作らない。

## .gitignore 方針

**追跡しない**: 依存(`node_modules/`,`.venv/`)・ビルド生成物(`.next/`,`dist/`,`*.egg-info/`)・キャッシュ(`.mypy_cache/`,`.ruff_cache/`,`.pytest_cache/`)・秘密(`.env`,`*.pem`,`*.key`)・ローカル状態(`logs/`,`*.log`,`infra/volumes/`)・OS/エディタ(`.DS_Store`,`.idea/`)。

**追跡する**: `.env.example` など雛形は `!` で明示的に含める。

言語別の代表エントリは本リポジトリ `.gitignore` を雛形として流用する。

## チェックリスト（コミット前）

- [ ] 変更は単一の機能/修正に閉じているか
- [ ] prefix は add/update/fix/delete のいずれか
- [ ] 生成物・秘密が含まれていないか（`git status`/`git diff --staged` 確認）
- [ ] テスト/リンタ/型チェックが通るか
