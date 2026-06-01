"""「エラーは境界で1度だけログる」原則の構造ガードレール。

[ログ規約](../../../../docs/observability/logging-spec.md) §5,§10 を構造で固定する:

- ドメイン層は可観測性に依存しない(``domain は外向き依存ゼロ`` / architecture.md)。
- ドメイン/アプリケーション層は **エラー段階のログを出さない**(WARN/ERROR/exception)。
  失敗は例外を ``raise`` するだけで、ログは interface 層の最外郭(例外ハンドラ)に集約する。
  これにより log-and-rethrow による重複ログ(ERROR アラートの歪み)を防ぐ。

業務イベントの ``INFO`` ログ(``note.created`` 等)はアプリケーション層でも許容する
(エラーログとは別物)。
"""

from __future__ import annotations

import ast
from pathlib import Path

import flownote_api

_PACKAGE_ROOT = Path(flownote_api.__file__).resolve().parent
_DOMAIN_DIR = _PACKAGE_ROOT / "domain"
_APPLICATION_DIR = _PACKAGE_ROOT / "application"

# 境界(interface 層)にのみ許されるエラー段階のログメソッド名。
_ERROR_LEVEL_METHODS = frozenset({"warning", "warn", "error", "exception", "critical", "fatal"})


def _python_files(directory: Path) -> list[Path]:
    """ディレクトリ配下の Python ソースを列挙する(キャッシュ除く)。

    Args:
        directory: 探索対象ディレクトリ。

    Returns:
        ``.py`` ファイルの一覧。
    """
    return [p for p in directory.rglob("*.py") if "__pycache__" not in p.parts]


def _imports_observability(tree: ast.AST) -> bool:
    """構文木が ``flownote_observability`` を import しているか判定する。

    Args:
        tree: 解析済み AST。

    Returns:
        可観測性パッケージへの依存があれば ``True``。
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "flownote_observability"
        ):
            return True
        if isinstance(node, ast.Import) and any(
            alias.name.startswith("flownote_observability") for alias in node.names
        ):
            return True
    return False


def _error_level_log_calls(tree: ast.AST) -> list[str]:
    """エラー段階のログ呼び出し(``.error()`` 等・``exc_info=`` 付き)を抽出する。

    Args:
        tree: 解析済み AST。

    Returns:
        検出した呼び出しの説明文字列の一覧。
    """
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # `_logger.error(...)` のような属性呼び出しのメソッド名で判定する。
        if isinstance(node.func, ast.Attribute) and node.func.attr in _ERROR_LEVEL_METHODS:
            found.append(f"{node.func.attr}() @ line {node.lineno}")
        # exc_info=... を伴う呼び出しも例外ログとみなす。
        if any(kw.arg == "exc_info" for kw in node.keywords):
            found.append(f"exc_info= @ line {node.lineno}")
    return found


def test_domain_layer_is_observability_free() -> None:
    # ドメイン層は可観測性へ依存しない(純粋・ログを持たない)。
    offenders = [
        str(path.relative_to(_PACKAGE_ROOT))
        for path in _python_files(_DOMAIN_DIR)
        if _imports_observability(ast.parse(path.read_text(encoding="utf-8")))
    ]
    assert offenders == [], f"ドメイン層が可観測性に依存している: {offenders}"


def test_domain_and_application_do_not_log_errors() -> None:
    # ドメイン/アプリケーション層はエラー段階のログを出さない(境界に集約)。
    offenders: dict[str, list[str]] = {}
    for directory in (_DOMAIN_DIR, _APPLICATION_DIR):
        for path in _python_files(directory):
            calls = _error_level_log_calls(ast.parse(path.read_text(encoding="utf-8")))
            if calls:
                offenders[str(path.relative_to(_PACKAGE_ROOT))] = calls
    assert offenders == {}, f"境界外でエラーログを出している(log-and-rethrow 疑い): {offenders}"
