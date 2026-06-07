"""エラーコードの抽出コマンド(ドメイン＋境界の完全カタログを出力)。

クライアントに返る**全公開エラーコード**を1つの源泉
([interface/http/error_catalog.py] の :func:`full_error_catalog`)から抽出し、
Markdown / JSON / CSV で出力する。``--check`` は既存の生成物との差分を検出して
CI で「コード追加時のドキュメント追従漏れ」を弾くために使う。

使い方(リポジトリルートから):
    uv run --package flownote-api flownote-error-catalog                 # Markdown 表
    uv run --package flownote-api flownote-error-catalog --format json   # JSON
    uv run --package flownote-api flownote-error-catalog --format csv    # CSV
    uv run --package flownote-api flownote-error-catalog --format ts     # TypeScript(フロント共有)
    uv run --package flownote-api flownote-error-catalog --origin interface  # 境界のみ
    uv run --package flownote-api flownote-error-catalog --sort status   # ステータス順
    # 生成物の再生成 / CI での差分チェック:
    uv run --package flownote-api flownote-error-catalog -o docs/observability/error-catalog.md
    uv run --package flownote-api flownote-error-catalog --check docs/observability/error-catalog.md

設計上、本コマンドは出力生成に徹し、副作用(ファイル書き込み)は ``-o`` 指定時のみに限る。
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict
from pathlib import Path

from flownote_api.domain.errors import ErrorCatalogEntry
from flownote_api.interface.http.error_catalog import full_error_catalog

# origin フィルタの選択肢。
_ORIGINS = ("all", "domain", "interface")

# ソートキー → 並べ替え関数。いずれもコードを最終タイブレークにして安定化する。
_SORTS: dict[str, Callable[[ErrorCatalogEntry], tuple[object, ...]]] = {
    "code": lambda e: (e.code, e.origin),
    "status": lambda e: (e.http_status, e.code),
    "origin": lambda e: (e.origin, e.code),
}

# Markdown / CSV の列見出し(順序は両形式で一致させる)。
_HEADERS = ("コード", "HTTP", "origin", "タイトル", "公開詳細", "発行元")

# 生成物先頭に置く「自動生成」注記。--check 比較を成立させるため出力に常に含める。
_GENERATED_NOTE = (
    "# エラーコードカタログ（自動生成）\n\n"
    "> このファイルは `flownote-error-catalog` が生成する。**手で編集しない**。\n"
    "> 再生成 / 差分チェックは [apps/api README](../../apps/api/README.md) を参照。\n"
)


def _row(entry: ErrorCatalogEntry) -> tuple[str, str, str, str, str, str]:
    """カタログ項目を文字列タプル(表示用の1行)へ変換する。

    Args:
        entry: カタログ項目。

    Returns:
        ``_HEADERS`` に対応する6列の文字列。空の公開詳細は ``—`` で表す。
    """
    return (
        entry.code,
        str(entry.http_status),
        entry.origin,
        entry.public_title,
        entry.public_detail or "—",
        entry.source,
    )


def render_markdown(entries: list[ErrorCatalogEntry]) -> str:
    """カタログを Markdown 表(自動生成注記つき)へ整形する。

    Args:
        entries: 出力対象のカタログ項目。

    Returns:
        末尾改行つきの Markdown 文字列。
    """
    lines = [
        _GENERATED_NOTE,
        "| " + " | ".join(_HEADERS) + " |",
        "|" + "|".join(["---"] * len(_HEADERS)) + "|",
    ]
    lines.extend("| " + " | ".join(_row(entry)) + " |" for entry in entries)
    return "\n".join(lines) + "\n"


def render_json(entries: list[ErrorCatalogEntry]) -> str:
    """カタログを整形済み JSON 配列へ変換する。

    Args:
        entries: 出力対象のカタログ項目。

    Returns:
        末尾改行つきの JSON 文字列(キー順は安定)。
    """
    payload = [asdict(entry) for entry in entries]
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_csv(entries: list[ErrorCatalogEntry]) -> str:
    """カタログを CSV へ変換する(表計算/突合向け)。

    Args:
        entries: 出力対象のカタログ項目。

    Returns:
        ヘッダ行を含む CSV 文字列(改行は ``\\n`` に統一)。
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_HEADERS)
    writer.writerows(_row(entry) for entry in entries)
    return buffer.getvalue()


def render_ts(entries: list[ErrorCatalogEntry]) -> str:
    """カタログを TypeScript モジュールへ変換する(フロント共有用)。

    バックエンドの SSOT と一致する ``ErrorCode`` union 型・``ERROR_CATALOG`` 定数を生成し、
    フロントが手書きせずに同じコード集合で分岐できるようにする。生成物であり手編集しない。

    Args:
        entries: 出力対象のカタログ項目(コード昇順)。

    Returns:
        末尾改行つきの TypeScript ソース。
    """
    lines = [
        "// 自動生成: `flownote-error-catalog --format ts`。手で編集しない。",
        "// 生成元はバックエンドの SSOT (domain/errors.py + interface/http/error_catalog.py)。",
        "",
        "/** クライアントに返りうる安定エラーコード(ドメイン＋境界)。 */",
        "export const ERROR_CODES = [",
    ]
    lines.extend(f'  "{entry.code}",' for entry in entries)
    lines.extend(
        [
            "] as const;",
            "",
            "/** 安定エラーコードの union 型。 */",
            "export type ErrorCode = (typeof ERROR_CODES)[number];",
            "",
            "/** エラーカタログの1項目。 */",
            "export interface ErrorCatalogEntry {",
            "  /** HTTP ステータス。 */",
            "  httpStatus: number;",
            "  /** 発行レイヤ(domain=ドメイン例外 / interface=境界発行)。 */",
            '  origin: "domain" | "interface";',
            "  /** 公開表題。 */",
            "  title: string;",
            "}",
            "",
            "/** コード → 定義の対応表。 */",
            "export const ERROR_CATALOG: Record<ErrorCode, ErrorCatalogEntry> = {",
        ]
    )
    for entry in entries:
        title = json.dumps(entry.public_title, ensure_ascii=False)
        lines.append(
            f'  "{entry.code}": {{ httpStatus: {entry.http_status}, '
            f'origin: "{entry.origin}", title: {title} }},'
        )
    lines.append("};")
    return "\n".join(lines) + "\n"


_FORMATS = {
    "markdown": render_markdown,
    "json": render_json,
    "csv": render_csv,
    "ts": render_ts,
}


def _select(origin: str, sort: str) -> list[ErrorCatalogEntry]:
    """完全カタログを取得し、origin で絞り込み指定キーで並べ替える。

    Args:
        origin: ``all`` / ``domain`` / ``interface``。
        sort: ``code`` / ``status`` / ``origin``。

    Returns:
        フィルタ・ソート済みのカタログ項目。
    """
    entries = full_error_catalog()
    if origin != "all":
        entries = [entry for entry in entries if entry.origin == origin]
    return sorted(entries, key=_SORTS[sort])


def _build_parser() -> argparse.ArgumentParser:
    """引数パーサを構築する。

    Returns:
        構成済みの :class:`argparse.ArgumentParser`。
    """
    parser = argparse.ArgumentParser(
        prog="flownote-error-catalog",
        description="クライアントに返る全公開エラーコードを抽出する(ドメイン＋境界)。",
    )
    parser.add_argument(
        "--format", choices=tuple(_FORMATS), default="markdown", help="出力形式(既定: markdown)"
    )
    parser.add_argument(
        "--origin", choices=_ORIGINS, default="all", help="発行レイヤで絞り込む(既定: all)"
    )
    parser.add_argument(
        "--sort", choices=tuple(_SORTS), default="code", help="並べ替えキー(既定: code)"
    )
    # 書き出し(-o)と差分検査(--check)は排他。併用時の黙殺を避ける。
    sink = parser.add_mutually_exclusive_group()
    sink.add_argument(
        "-o", "--output", type=Path, default=None, help="出力先ファイル(省略時は標準出力)"
    )
    sink.add_argument(
        "--check",
        type=Path,
        default=None,
        metavar="FILE",
        help="指定ファイルと出力を比較し、差分があれば非ゼロ終了(CI 用)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """エントリポイント。引数を解釈してカタログを出力(または差分検査)する。

    Args:
        argv: コマンドライン引数(省略時は ``sys.argv``)。

    Returns:
        終了コード。``--check`` で差分があれば 1、それ以外は 0。
    """
    args = _build_parser().parse_args(argv)
    # argparse の属性は実質 Any のため、ここで具体型へ確定させてから扱う。
    fmt = str(args.format)
    origin = str(args.origin)
    sort_key = str(args.sort)
    check_path: Path | None = args.check
    output_path: Path | None = args.output

    rendered = _FORMATS[fmt](_select(origin, sort_key))

    if check_path is not None:
        current = check_path.read_text(encoding="utf-8") if check_path.exists() else ""
        if current == rendered:
            return 0
        sys.stderr.write(
            f"エラーカタログが {check_path} と一致しません。"
            "再生成してください: `flownote-error-catalog -o <path>`\n"
        )
        return 1

    if output_path is not None:
        output_path.write_text(rendered, encoding="utf-8")
        return 0

    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":  # pragma: no cover - 手動実行用
    raise SystemExit(main())
