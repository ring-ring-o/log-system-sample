"""テレメトリ語彙の抽出コマンド(FE 共有用の TypeScript を生成)。

FE/BE で一致が必要な値(API ルートのフルパス・共有テレメトリ属性キー)を
バックエンドの SSOT([interface/telemetry_catalog.py])から TypeScript モジュールへ生成する。
``--check`` は既存生成物との差分を検出し、CI で「BE 変更時のフロント追従漏れ」を弾く。

使い方(リポジトリルートから):
    uv run --package flownote-api flownote-telemetry-catalog --target routes \
        -o apps/web/src/shared/routes.generated.ts
    uv run --package flownote-api flownote-telemetry-catalog --target semconv \
        -o packages/observability-web/src/semconv.ts
    # CI での差分チェック:
    uv run --package flownote-api flownote-telemetry-catalog --target routes \
        --check apps/web/src/shared/routes.generated.ts

設計上、本コマンドは出力生成に徹し、副作用(ファイル書き込み)は ``-o`` 指定時のみに限る。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from flownote_api.interface.telemetry_catalog import shared_attributes, shared_routes

_GEN_HEADER = "// 自動生成: `flownote-telemetry-catalog --target {target}`。手で編集しない。"
_GEN_SOURCE = "// 生成元はバックエンドの SSOT (flownote_api.interface.telemetry_catalog)。"


def render_ts_routes() -> str:
    """フロント共有ルートを TypeScript モジュールへ変換する。

    Returns:
        末尾改行つきの TypeScript ソース(``API_ROUTES`` 定数)。
    """
    lines = [
        _GEN_HEADER.format(target="routes"),
        _GEN_SOURCE,
        "",
        "/** フロントが呼び出す API ルートのフルパス(バックエンド SSOT と一致)。 */",
        "export const API_ROUTES = {",
    ]
    for route in shared_routes():
        lines.append(f"  {route.name}: {json.dumps(route.path, ensure_ascii=False)},")
    lines.extend(
        [
            "} as const;",
            "",
            "/** ルート名の union 型。 */",
            "export type ApiRouteName = keyof typeof API_ROUTES;",
        ]
    )
    return "\n".join(lines) + "\n"


def render_ts_semconv() -> str:
    """共有テレメトリ属性キーを TypeScript モジュールへ変換する。

    Returns:
        末尾改行つきの TypeScript ソース(``ATTR`` 定数)。
    """
    lines = [
        _GEN_HEADER.format(target="semconv"),
        _GEN_SOURCE,
        "",
        "/** FE/BE が共有するテレメトリ属性/リソースキー(OTel/FlowNote)。 */",
        "export const ATTR = {",
    ]
    for attr in shared_attributes():
        lines.append(
            f"  /** {attr.intent}。 */\n"
            f"  {attr.ts_name}: {json.dumps(attr.key, ensure_ascii=False)},"
        )
    lines.extend(
        [
            "} as const;",
            "",
            "/** 共有属性キー名の union 型。 */",
            "export type AttrName = keyof typeof ATTR;",
        ]
    )
    return "\n".join(lines) + "\n"


_TARGETS = {
    "routes": render_ts_routes,
    "semconv": render_ts_semconv,
}


def _build_parser() -> argparse.ArgumentParser:
    """引数パーサを構築する。

    Returns:
        構成済みの :class:`argparse.ArgumentParser`。
    """
    parser = argparse.ArgumentParser(
        prog="flownote-telemetry-catalog",
        description="FE/BE 共有のテレメトリ語彙(ルート/属性キー)を TypeScript へ生成する。",
    )
    parser.add_argument(
        "--target", choices=tuple(_TARGETS), required=True, help="生成対象(routes / semconv)"
    )
    # 形式は TypeScript のみ(FE 共有が目的)。将来の拡張に備え引数自体は残す。
    parser.add_argument("--format", choices=("ts",), default="ts", help="出力形式(既定: ts)")
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
    """エントリポイント。対象を生成(または差分検査)する。

    Args:
        argv: コマンドライン引数(省略時は ``sys.argv``)。

    Returns:
        終了コード。``--check`` で差分があれば 1、それ以外は 0。
    """
    args = _build_parser().parse_args(argv)
    target = str(args.target)
    check_path: Path | None = args.check
    output_path: Path | None = args.output

    rendered = _TARGETS[target]()

    if check_path is not None:
        current = check_path.read_text(encoding="utf-8") if check_path.exists() else ""
        if current == rendered:
            return 0
        sys.stderr.write(
            f"テレメトリカタログ({target})が {check_path} と一致しません。"
            "再生成してください: `flownote-telemetry-catalog --target "
            f"{target} -o <path>`\n"
        )
        return 1

    if output_path is not None:
        output_path.write_text(rendered, encoding="utf-8")
        return 0

    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":  # pragma: no cover - 手動実行用
    raise SystemExit(main())
