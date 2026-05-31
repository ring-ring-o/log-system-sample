"""機密情報のマスキング。

[マスキング規約](../../../docs/observability/redaction-policy.md) を実装する。
全ロガー/トレース属性/GenAI ヘルパはこのモジュールの :func:`redact` を経由し、
機密フィールド名・機密値パターンを不可逆にマスクする。
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

# マスク後の置換文字列。
_MASK = "***"

# キー名(小文字・部分一致)が機密とみなされる語。値ごと :data:`_MASK` に置換する。
SENSITIVE_KEY_PARTS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "authorization",
        "api_key",
        "apikey",
        "client_secret",
        "cookie",
        "set-cookie",
        "private_key",
        "credential",
        "session",
        "otp",
    }
)

# 値の中身が機密とみなされる正規表現と、その置換後文字列。
_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # JWT (3 セグメントの base64url)。
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "***JWT***"),
    # Bearer トークン。
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"), "Bearer ***"),
    # 代表的な API キー形 (sk-... 等)。
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), _MASK),
    # メールアドレス (準PII。規約に従いマスク)。
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "***@***"),
)

# 再帰の暴走(DoS)を防ぐための上限。
_MAX_DEPTH = 12
_MAX_ITEMS = 5_000


def _is_sensitive_key(key: str) -> bool:
    """キー名が機密語を含むか判定する。

    Args:
        key: 属性キー名。

    Returns:
        小文字化して :data:`SENSITIVE_KEY_PARTS` のいずれかを部分一致で含めば ``True``。
    """
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _redact_str(value: str) -> str:
    """文字列値に含まれる機密パターンをマスクする。

    Args:
        value: 元の文字列。

    Returns:
        機密パターンを置換した文字列。
    """
    result = value
    for pattern, replacement in _VALUE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact(value: object, *, _depth: int = 0) -> object:
    """任意のログ属性値を再帰的にマスクする。

    dict/list を再帰的に走査し、機密キーは値ごと、文字列値は機密パターンをマスクする。
    値の型情報は保つ(構造化ログのスキーマを壊さない)。``object`` を引数に取るのは、
    ログ属性が任意の Python 値になりうる境界だからである。

    Args:
        value: マスク対象の値 (dict/list/str/数値/None 等)。
        _depth: 内部用の再帰深さ。呼び出し側は指定しない。

    Returns:
        マスク適用後の同型の値。深さ上限を超えた場合は :data:`_MASK` を返す。
    """
    if _depth > _MAX_DEPTH:
        return _MASK

    if isinstance(value, str):
        return _redact_str(value)

    # dict は再帰。機密キーは値を見ずにマスクする。
    if isinstance(value, Mapping):
        redacted: dict[str, object] = {}
        for raw_key, item in list(value.items())[:_MAX_ITEMS]:
            key = str(raw_key)
            if _is_sensitive_key(key):
                redacted[key] = _MASK
            else:
                redacted[key] = redact(item, _depth=_depth + 1)
        return redacted

    # str 以外の Sequence (list/tuple) は各要素を再帰。
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [redact(item, _depth=_depth + 1) for item in list(value)[:_MAX_ITEMS]]

    # bytes はそのまま長さのみ示す(本文を出さない)。
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"

    # 数値/bool/None 等はそのまま返す。
    return value
