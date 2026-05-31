"use client";

/**
 * メモ一覧・作成パネル。
 *
 * 計装済み API クライアントを通じてバックエンドを呼ぶ(フロント→バックの相関ログが出る)。
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/Button";
import { type Note, createApiClient } from "@/shared/api-client";
import { getClientLogger } from "@/shared/observability";
import { useToken } from "@/shared/use-token";
import { color, font, radius, space } from "@/tokens/tokens";

/**
 * メモ機能のパネル。
 *
 * @returns パネル要素。
 */
export function NotesPanel() {
  const token = useToken();
  const [notes, setNotes] = useState<Note[]>([]);
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);

  // トークンが変わったときだけ API クライアントを作り直す(安定参照)。
  const api = useMemo(() => createApiClient(() => token), [token]);

  const reload = useCallback(async () => {
    try {
      setNotes(await api.listNotes());
      setError(null);
    } catch {
      setError("メモの取得に失敗しました");
      getClientLogger().warn("web.notes.load_failed");
    }
  }, [api]);

  useEffect(() => {
    void reload();
  }, [reload]);

  /**
   * フォーム送信でメモを作成する。
   */
  async function handleCreate(): Promise<void> {
    if (!title.trim()) return;
    try {
      await api.createNote({ title, body: "" });
      // ユーザー操作イベント(本文は記録しない)。
      getClientLogger().info("web.note.created", { "flownote.web.action": "create_note" });
      setTitle("");
      await reload();
    } catch {
      setError("メモの作成に失敗しました");
    }
  }

  return (
    <section style={{ padding: space[4], borderRadius: radius.md, background: color.bgSubtle }}>
      <h2 style={{ fontSize: font.sizeLg }}>メモ</h2>
      <div style={{ display: "flex", gap: space[2], marginBottom: space[4] }}>
        <input
          aria-label="メモのタイトル"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="新しいメモのタイトル"
          style={{ flex: 1, padding: space[2] }}
        />
        <Button onClick={() => void handleCreate()}>作成</Button>
      </div>
      {error && <p style={{ color: color.dangerFg }}>{error}</p>}
      <ul>
        {notes.map((note) => (
          <li key={note.id}>{note.title}</li>
        ))}
      </ul>
    </section>
  );
}
