/**
 * Storybook プレビュー設定。デザイントークン(CSS変数)を読み込む。
 */
import type { Preview } from "@storybook/react";

import "../src/app/globals.css";

const preview: Preview = {
  parameters: {
    controls: { matchers: { color: /(background|color)$/i, date: /Date$/i } },
  },
};

export default preview;
