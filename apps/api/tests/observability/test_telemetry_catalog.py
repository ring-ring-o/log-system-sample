"""テレメトリ語彙の抽出(共有カタログ＋CLI)の契約テスト。

FE/BE で一致が必要な値(ルートパス・共有属性キー)を BE の SSOT から TypeScript へ生成できること、
``--check`` でドリフトを検知できること、リポジトリ内の生成物が最新であることを固定する
(error-catalog と同じ「SSOT → 生成 → --check」方式)。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from flownote_api.interface.cli import telemetry_catalog as cli
from flownote_api.interface.telemetry_catalog import shared_attributes, shared_routes

# リポジトリルート(本ファイル: <root>/apps/api/tests/observability/...)。
_REPO_ROOT = Path(__file__).resolve().parents[4]
_ROUTES_TS = _REPO_ROOT / "apps/web/src/shared/routes.generated.ts"
_SEMCONV_TS = _REPO_ROOT / "packages/observability-web/src/semconv.ts"


def test_shared_routes_are_full_paths() -> None:
    routes = {route.name: route.path for route in shared_routes()}
    # フロントが叩くフルパス(BE prefix + サブパスから合成)を固定する。
    assert routes["NOTES"] == "/api/notes"
    assert routes["AI_SEARCH"] == "/api/ai/search"
    assert routes["AI_CONSULT"] == "/api/ai/consult"


def test_shared_attributes_include_resource_and_error_keys() -> None:
    attrs = {attr.ts_name: attr.key for attr in shared_attributes()}
    assert attrs["DEPLOYMENT_ENVIRONMENT"] == "deployment.environment.name"
    assert attrs["HTTP_RESPONSE_STATUS_CODE"] == "http.response.status_code"
    assert attrs["FLOWNOTE_ERROR_CODE"] == "flownote.error.code"


def test_cli_routes_ts_emits_const_and_paths(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--target", "routes"]) == 0
    out = capsys.readouterr().out
    assert "export const API_ROUTES" in out
    assert '"/api/ai/search"' in out


def test_cli_semconv_ts_emits_attr_object(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--target", "semconv"]) == 0
    out = capsys.readouterr().out
    assert "export const ATTR" in out
    assert '"deployment.environment.name"' in out


def test_cli_requires_target() -> None:
    # --target は必須(誤って空生成しない)。
    with pytest.raises(SystemExit):
        cli.main([])


def test_cli_output_and_check_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):
        cli.main(["--target", "routes", "-o", "x.ts", "--check", "x.ts"])


def test_cli_check_detects_drift(tmp_path: Path) -> None:
    snapshot = tmp_path / "routes.generated.ts"
    assert cli.main(["--target", "routes", "-o", str(snapshot)]) == 0
    assert cli.main(["--target", "routes", "--check", str(snapshot)]) == 0
    snapshot.write_text("stale\n", encoding="utf-8")
    assert cli.main(["--target", "routes", "--check", str(snapshot)]) == 1


def test_repository_generated_files_are_current() -> None:
    # リポジトリにコミットされた生成物が SSOT と一致する(追従漏れの防止)。
    assert cli.main(["--target", "routes", "--check", str(_ROUTES_TS)]) == 0
    assert cli.main(["--target", "semconv", "--check", str(_SEMCONV_TS)]) == 0
