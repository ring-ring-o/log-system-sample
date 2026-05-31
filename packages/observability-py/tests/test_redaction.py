"""マスキング規約のテスト([redaction-policy] の固定)。"""

from __future__ import annotations

from flownote_observability.redaction import redact


def test_sensitive_keys_are_masked() -> None:
    # 機密キー(部分一致)は値ごとマスクされる。
    result = redact(
        {
            "password": "p@ss",
            "Authorization": "Bearer abc.def",
            "access_token": "xyz",
            "Cookie": "sid=1",
            "note": "safe",
        }
    )
    assert isinstance(result, dict)
    assert result["password"] == "***"
    assert result["Authorization"] == "***"
    assert result["access_token"] == "***"
    assert result["Cookie"] == "***"
    # 非機密キーは保持される。
    assert result["note"] == "safe"


def test_value_patterns_are_masked() -> None:
    # キー名が機密でなくても、値中の JWT/Bearer/メールはマスクされる。
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcDEF_-123"
    result = redact({"text": f"token={jwt} mail alice@example.com"})
    assert isinstance(result, dict)
    masked = result["text"]
    assert isinstance(masked, str)
    assert jwt not in masked
    assert "***JWT***" in masked
    assert "alice@example.com" not in masked
    assert "***@***" in masked


def test_nested_structures_are_masked() -> None:
    # ネストした dict/list の中の機密も再帰的にマスクされる。
    result = redact({"outer": {"secret": "s", "items": [{"api_key": "k"}, "alice@example.com"]}})
    assert isinstance(result, dict)
    outer = result["outer"]
    assert isinstance(outer, dict)
    assert outer["secret"] == "***"
    items = outer["items"]
    assert isinstance(items, list)
    first = items[0]
    assert isinstance(first, dict)
    assert first["api_key"] == "***"
    assert items[1] == "***@***"


def test_non_string_values_are_preserved() -> None:
    # 数値/真偽/None は型を保ったまま通過する(スキーマを壊さない)。
    result = redact({"count": 3, "ok": True, "missing": None})
    assert result == {"count": 3, "ok": True, "missing": None}


def test_recursion_depth_is_bounded() -> None:
    # 深いネストでも例外を出さず、上限超過は伏字になる(DoS 対策)。
    deep: dict[str, object] = {}
    cursor = deep
    for _ in range(50):
        nxt: dict[str, object] = {}
        cursor["child"] = nxt
        cursor = nxt
    result = redact(deep)
    assert result is not None
