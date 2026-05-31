/**
 * ルートレイアウト。
 */

import type { ReactNode } from "react";

import { Providers } from "@/components/Providers";

import "./globals.css";

/** ページメタデータ。 */
export const metadata = {
  title: "FlowNote",
  description: "Markdownメモ・タスク・バージョン管理を AI が支援する統合ワークスペース",
};

/**
 * ルートレイアウト。
 *
 * @param props - 子要素。
 * @returns HTML ルート。
 */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ja">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
