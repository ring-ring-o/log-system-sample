"use client";

/**
 * 認証トークン取得フック。
 *
 * セッション(Keycloak)のアクセストークンを返す。ローカルで Keycloak を立てない場合は
 * `NEXT_PUBLIC_DEV_TOKEN`(例: ``alice:editor``)にフォールバックし、API の dev 認証で動かせる。
 */

import { useSession } from "next-auth/react";

/**
 * 現在のアクセストークンを返す。
 *
 * @returns トークン文字列(無ければ undefined)。
 */
export function useToken(): string | undefined {
  const { data } = useSession();
  if (data?.accessToken) return data.accessToken;
  // dev トークンのフォールバックは本番ビルドでは無効化する(バンドルへの秘密焼き込み防止)。
  if (process.env.NODE_ENV !== "production") {
    return process.env.NEXT_PUBLIC_DEV_TOKEN;
  }
  return undefined;
}
