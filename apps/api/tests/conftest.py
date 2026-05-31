"""apps/api テスト共通設定。

テストを外部依存なし・低ノイズで回すため、アプリ import より前に環境変数を設定する
(インメモリDB / AIスタブ / 開発認証 / コンソールエクスポート無効)。
"""

from __future__ import annotations

import os

# create_app() が import 時に環境変数を読むため、ここで先に既定値を設定する。
os.environ.setdefault("FLOWNOTE_ENV", "local")
os.environ.setdefault("FLOWNOTE_OTEL_CONSOLE", "0")
os.environ.setdefault("FLOWNOTE_REPO_BACKEND", "memory")
os.environ.setdefault("FLOWNOTE_AI_BACKEND", "stub")
os.environ.setdefault("FLOWNOTE_AUTH_MODE", "dev")
