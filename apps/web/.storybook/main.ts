/**
 * Storybook 設定。
 *
 * 有効化するには storybook を導入する: `pnpm --filter web add -D storybook @storybook/react-vite`。
 * Next.js 16(beta)とのピア整合を避けるため、UIプリミティブの確認には react-vite フレームワークを用いる。
 */
import type { StorybookConfig } from "@storybook/react-vite";

const config: StorybookConfig = {
  stories: ["../src/**/*.stories.@(ts|tsx)"],
  framework: { name: "@storybook/react-vite", options: {} },
  addons: [],
};

export default config;
