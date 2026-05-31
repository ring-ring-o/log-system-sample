/**
 * Button の Storybook ストーリー。
 *
 * 注: tsc/Next ビルドからは除外している(storybook 未導入でも型エラーにしないため)。
 * storybook 導入後に `pnpm --filter web storybook` で確認できる。
 */
import type { Meta, StoryObj } from "@storybook/react";

import { Button } from "./Button";

const meta: Meta<typeof Button> = {
  title: "components/Button",
  component: Button,
  args: { children: "保存" },
};

export default meta;

type Story = StoryObj<typeof Button>;

/** 主要操作のボタン。 */
export const Primary: Story = { args: { intent: "primary" } };

/** 副次操作のボタン。 */
export const Secondary: Story = { args: { intent: "secondary", children: "キャンセル" } };
