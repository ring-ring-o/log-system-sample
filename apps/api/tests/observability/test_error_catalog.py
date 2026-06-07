"""エラーコード抽出(統合カタログ＋CLI)の契約テスト。

[ログ規約](../../../../docs/observability/logging-spec.md) §5 のエラー設計を運用面で固定する。
ここで固定するのは「ドメイン＋境界の全公開コードが1点から抽出できる」「境界コードは
ハンドラと同じ SSOT を参照する」「抽出コマンドが Markdown/JSON/CSV と差分検査を提供する」。
"""

from __future__ import annotations

import json

import pytest

from flownote_api.interface.cli import error_catalog as cli
from flownote_api.interface.http.error_catalog import (
    AUTH_UNAUTHORIZED,
    BOUNDARY_ERRORS,
    VAL_REQUEST,
    boundary_catalog,
    full_error_catalog,
)

# クライアントに返る全公開コード(ドメイン＋境界)。回帰防止のため明示する。
_EXPECTED_CODES = {
    "RES.NOT_FOUND",
    "AUTHZ.DENIED",
    "VAL.INVALID",
    "RES.CONFLICT",
    "GEN.INTERNAL",
    "AUTH.UNAUTHORIZED",
    "VAL.REQUEST",
}


def test_full_catalog_covers_domain_and_boundary() -> None:
    catalog = full_error_catalog()
    codes = [entry.code for entry in catalog]
    # ドメイン例外と境界発行コードの双方が、漏れも重複もなく揃う。
    assert set(codes) == _EXPECTED_CODES
    assert len(codes) == len(set(codes))
    # (code, origin) で安定ソートされている(生成物の差分を小さく保つ)。
    assert catalog == sorted(catalog, key=lambda e: (e.code, e.origin))


def test_boundary_codes_are_tagged_interface() -> None:
    # 境界由来は origin=interface で、公開詳細を静的に持つ。
    boundary = boundary_catalog()
    assert {entry.code for entry in boundary} == {"AUTH.UNAUTHORIZED", "VAL.REQUEST"}
    assert {entry.origin for entry in boundary} == {"interface"}
    assert all(entry.public_detail for entry in boundary)


def test_boundary_registry_is_single_source() -> None:
    # ハンドラが参照する定数が SSOT 一覧に含まれる(リテラル散在の防止を固定)。
    assert AUTH_UNAUTHORIZED in BOUNDARY_ERRORS
    assert VAL_REQUEST in BOUNDARY_ERRORS


def test_cli_json_is_machine_readable(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert {entry["code"] for entry in payload} == _EXPECTED_CODES
    # 各項目はフィルタ/ソートに使うフィールドを保持する。
    assert all({"code", "http_status", "origin", "source"} <= entry.keys() for entry in payload)


def test_cli_csv_has_header_and_rows(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--format", "csv"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0].startswith("コード,")
    assert len(lines) == len(_EXPECTED_CODES) + 1  # ヘッダ + 全コード


def test_cli_markdown_contains_note_and_codes(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([]) == 0  # 既定は Markdown
    out = capsys.readouterr().out
    assert "自動生成" in out
    assert "AUTH.UNAUTHORIZED" in out and "GEN.INTERNAL" in out


def test_cli_markdown_table_shape_and_empty_detail(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("|")]
    # ヘッダ + 区切り + 全コード行。列順(コード→…→発行元)を固定する。
    assert lines[0] == "| コード | HTTP | origin | タイトル | 公開詳細 | 発行元 |"
    assert len(lines) == len(_EXPECTED_CODES) + 2
    # 公開詳細が静的に定まらないドメイン項目は `—` で表す(空セルにしない)。
    res_not_found = next(line for line in lines if line.startswith("| RES.NOT_FOUND "))
    assert " — " in res_not_found


def test_cli_ts_emits_union_and_catalog(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--format", "ts"]) == 0
    out = capsys.readouterr().out
    # フロント共有用に union 型とカタログ定数を生成し、全コードを含める。
    assert "export type ErrorCode" in out
    assert "export const ERROR_CATALOG: Record<ErrorCode, ErrorCatalogEntry>" in out
    for code in _EXPECTED_CODES:
        assert f'"{code}"' in out


def test_cli_output_and_check_are_mutually_exclusive() -> None:
    # 書き出しと差分検査の併用は argparse が拒否する(黙殺事故の防止)。
    with pytest.raises(SystemExit):
        cli.main(["-o", "x.md", "--check", "x.md"])


def test_cli_origin_filter_selects_only_interface(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--format", "json", "--origin", "interface"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert {entry["code"] for entry in payload} == {"AUTH.UNAUTHORIZED", "VAL.REQUEST"}


def test_cli_sort_by_status_orders_ascending(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--format", "json", "--sort", "status"]) == 0
    statuses = [entry["http_status"] for entry in json.loads(capsys.readouterr().out)]
    assert statuses == sorted(statuses)


def test_cli_check_detects_drift(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    snapshot = tmp_path / "error-catalog.md"
    # 生成物を書き出した直後は一致(終了コード 0)。
    assert cli.main(["-o", str(snapshot)]) == 0
    assert cli.main(["--check", str(snapshot)]) == 0
    # 内容が古くなれば差分として検知(非ゼロ終了)。
    snapshot.write_text("stale\n", encoding="utf-8")
    assert cli.main(["--check", str(snapshot)]) == 1


def test_cli_output_writes_file_without_stdout(
    tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_file = tmp_path / "catalog.json"
    assert cli.main(["--format", "json", "-o", str(out_file)]) == 0
    # -o 指定時は標準出力に書かず、ファイルにのみ出力する。
    assert capsys.readouterr().out == ""
    assert json.loads(out_file.read_text(encoding="utf-8"))
