"use client";

/**
 * AI 統合検索パネル。
 *
 * 検索クエリ本文はログに記録しない(操作イベントのみ)。結果はバックエンドの AI ユースケース由来。
 */

import { useState } from "react";

import { Button } from "@/components/Button";
import { type SearchHit, createApiClient } from "@/shared/api-client";
import { getClientLogger } from "@/shared/observability";
import { useToken } from "@/shared/use-token";
import { color, font, space } from "@/tokens/tokens";

/**
 * AI 統合検索のパネル。
 *
 * @returns パネル要素。
 */
export function SearchPanel() {
  const token = useToken();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const api = createApiClient(() => token);

  /**
   * 検索を実行する。
   */
  async function handleSearch(): Promise<void> {
    if (!query.trim()) return;
    // 操作イベントのみ記録(クエリ本文は載せない)。
    getClientLogger().info("web.search.executed", { "flownote.web.action": "unified_search" });
    setHits(await api.search(query));
  }

  return (
    <section style={{ padding: space[4], borderRadius: space[2], background: color.bgSubtle }}>
      <h2 style={{ fontSize: font.sizeLg }}>AI 統合検索</h2>
      <div style={{ display: "flex", gap: space[2], marginBottom: space[4] }}>
        <input
          aria-label="検索クエリ"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="メモ・タスクを横断検索"
          style={{ flex: 1, padding: space[2] }}
        />
        <Button onClick={() => void handleSearch()}>検索</Button>
      </div>
      <ul>
        {hits.map((hit) => (
          <li key={`${hit.kind}:${hit.id}`}>
            <span style={{ color: color.textMuted }}>[{hit.kind}]</span> {hit.title}{" "}
            <span style={{ color: color.textMuted }}>({hit.score})</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
