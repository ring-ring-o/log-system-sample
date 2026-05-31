"use client";

/**
 * ダッシュボード画面。
 *
 * 認証(Keycloak)とメモ/AI検索パネルをまとめる。ローカルで Keycloak を立てない場合は
 * `NEXT_PUBLIC_DEV_TOKEN` で API の dev 認証を使う。
 */

import { signIn, signOut, useSession } from "next-auth/react";

import { Button } from "@/components/Button";
import { SearchPanel } from "@/features/ai/SearchPanel";
import { NotesPanel } from "@/features/notes/NotesPanel";
import { font, space } from "@/tokens/tokens";

/**
 * ダッシュボード。
 *
 * @returns 画面要素。
 */
export function Dashboard() {
  const { data, status } = useSession();

  return (
    <main style={{ maxWidth: 800, margin: "0 auto", padding: space[6] }}>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: space[6],
        }}
      >
        <h1 style={{ fontSize: font.sizeXl }}>FlowNote</h1>
        {status === "authenticated" ? (
          <Button intent="secondary" onClick={() => void signOut()}>
            ログアウト({data?.user?.name ?? "ユーザー"})
          </Button>
        ) : (
          <Button onClick={() => void signIn("keycloak")}>Keycloak でログイン</Button>
        )}
      </header>
      <div style={{ display: "grid", gap: space[4] }}>
        <NotesPanel />
        <SearchPanel />
      </div>
    </main>
  );
}
