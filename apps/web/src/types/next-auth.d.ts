/**
 * Auth.js の型拡張。セッション/JWT にアクセストークンを持たせる。
 */

import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    /** バックエンド呼び出しに用いるアクセストークン。 */
    accessToken?: string;
    user?: DefaultSession["user"];
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    /** 保持したアクセストークン。 */
    accessToken?: string;
  }
}
