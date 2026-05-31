"""アクセストークンの検証アダプタ。

[ADR 0004](../../../../docs/adr/0004-auth-keycloak.md)。Keycloak(OIDC)発行の JWT を JWKS で検証する
実装と、Keycloak 無しでも動くローカル開発用実装を提供する。検証ポートを介すことで、テストは
フェイクに差し替えられる。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import jwt

from flownote_api.domain.identity import Role


class InvalidTokenError(Exception):
    """トークンが不正(署名/期限/aud/iss 等)であることを表す。

    Attributes:
        reason: 失敗理由の分類(``expired``/``invalid_signature`` 等)。
    """

    def __init__(self, reason: str) -> None:
        """エラーを生成する。

        Args:
            reason: 失敗理由の分類。
        """
        self.reason = reason
        super().__init__(f"トークンが不正です: {reason}")


@dataclass(frozen=True, slots=True)
class VerifiedToken:
    """検証済みトークンから得た主体情報。

    Attributes:
        subject: 不透明な主体ID(``sub``)。
        roles: 付与ロール(未知ロールは除外)。
    """

    subject: str
    roles: frozenset[Role]


def _parse_roles(raw_roles: object) -> frozenset[Role]:
    """ロール文字列のリストを既知の :class:`Role` 集合へ変換する。

    Args:
        raw_roles: トークンから得たロール表現(リスト想定)。

    Returns:
        既知ロールのみの集合。
    """
    if not isinstance(raw_roles, list):
        return frozenset()
    known = {role.value for role in Role}
    return frozenset(Role(item) for item in raw_roles if isinstance(item, str) and item in known)


class TokenVerifier(Protocol):
    """トークン検証ポート。"""

    async def verify(self, token: str) -> VerifiedToken:
        """トークンを検証し主体情報を返す。

        Args:
            token: Bearer トークン文字列。

        Returns:
            検証済み主体情報。

        Raises:
            InvalidTokenError: 検証に失敗した場合。
        """
        ...


class DevTokenVerifier:
    """ローカル開発用の簡易検証(Keycloak 不要)。

    トークンを ``<sub>`` または ``<sub>:role1,role2`` と解釈する。署名検証は行わないため、
    本番では決して使用しない(構成 ``auth_mode=dev`` 時のみ合成ルートが選択する)。
    """

    def __init__(self, *, default_roles: frozenset[Role]) -> None:
        """既定ロールで初期化する。

        Args:
            default_roles: ロール未指定トークンに与える既定ロール。
        """
        self._default_roles = default_roles

    async def verify(self, token: str) -> VerifiedToken:
        """開発用トークンを解釈する。

        Args:
            token: ``<sub>`` または ``<sub>:role1,role2``。

        Returns:
            主体情報。

        Raises:
            InvalidTokenError: トークンが空の場合。
        """
        if not token.strip():
            raise InvalidTokenError("empty")
        subject, _, roles_part = token.partition(":")
        if roles_part:
            roles = _parse_roles([r.strip() for r in roles_part.split(",")])
        else:
            roles = self._default_roles
        return VerifiedToken(subject=subject, roles=roles)


class KeycloakJwtVerifier:
    """Keycloak(OIDC)の JWT を JWKS で検証する実装。"""

    def __init__(self, *, jwks_url: str, issuer: str, audience: str) -> None:
        """検証パラメータで初期化する。

        Args:
            jwks_url: JWKS エンドポイントURL。
            issuer: 期待する発行者(``iss``)。
            audience: 期待する対象者(``aud``)。
        """
        self._issuer = issuer
        self._audience = audience
        # JWKS は内部でキャッシュされる。
        self._jwk_client = jwt.PyJWKClient(jwks_url)

    async def verify(self, token: str) -> VerifiedToken:
        """JWT の署名・期限・aud・iss を検証し主体情報を返す。

        Args:
            token: Bearer トークン(JWT)。

        Returns:
            検証済み主体情報。

        Raises:
            InvalidTokenError: 署名不正・期限切れ・クレーム不一致など。
        """
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            claims: dict[str, object] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
            )
        except jwt.ExpiredSignatureError as exc:
            raise InvalidTokenError("expired") from exc
        except jwt.InvalidSignatureError as exc:
            raise InvalidTokenError("invalid_signature") from exc
        except jwt.InvalidAudienceError as exc:
            raise InvalidTokenError("invalid_audience") from exc
        except jwt.InvalidIssuerError as exc:
            raise InvalidTokenError("invalid_issuer") from exc
        except jwt.PyJWTError as exc:
            raise InvalidTokenError("invalid") from exc

        subject = claims.get("sub")
        if not isinstance(subject, str):
            raise InvalidTokenError("missing_subject")
        realm_access = claims.get("realm_access")
        raw_roles = realm_access.get("roles") if isinstance(realm_access, dict) else None
        return VerifiedToken(subject=subject, roles=_parse_roles(raw_roles))
