/**
 * 認証(Auth.js v5 / Keycloak OIDC)。
 *
 * Keycloak でログインし、アクセストークンをセッションへ載せてバックエンド呼び出しに用いる
 * ([ADR 0004](../../../docs/adr/0004-auth-keycloak.md))。
 */

import NextAuth from "next-auth";
import Keycloak from "next-auth/providers/keycloak";

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Keycloak({
      clientId: process.env.AUTH_KEYCLOAK_ID,
      clientSecret: process.env.AUTH_KEYCLOAK_SECRET,
      issuer: process.env.AUTH_KEYCLOAK_ISSUER,
    }),
  ],
  callbacks: {
    /**
     * 初回サインイン時にアクセストークンを JWT へ保持する。
     */
    jwt({ token, account }) {
      if (account?.access_token) {
        token.accessToken = account.access_token;
      }
      return token;
    },
    /**
     * セッションへアクセストークンを公開する(API 呼び出し用)。
     */
    session({ session, token }) {
      // 拡張型(next-auth.d.ts)に合わせて明示的に文字列として載せる。
      session.accessToken = token.accessToken as string | undefined;
      return session;
    },
  },
});
