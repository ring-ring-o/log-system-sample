/**
 * 型付きデザイントークン。
 *
 * CSS 変数(globals.css)を参照する型安全なアクセサ。コンポーネントは生値を直書きせず、
 * semantic トークンのみを参照する(規約: .claude/skills/design-tokens/SKILL.md)。
 */

/** semantic な色トークン(CSS変数参照)。 */
export const color = {
  bgDefault: "var(--color-bg-default)",
  bgSubtle: "var(--color-bg-subtle)",
  textDefault: "var(--color-text-default)",
  textMuted: "var(--color-text-muted)",
  borderDefault: "var(--color-border-default)",
  primaryBg: "var(--color-intent-primary-bg)",
  primaryFg: "var(--color-intent-primary-fg)",
  primaryHover: "var(--color-intent-primary-hover)",
  successFg: "var(--color-intent-success-fg)",
  warningFg: "var(--color-intent-warning-fg)",
  dangerFg: "var(--color-intent-danger-fg)",
} as const;

/** スペーシングトークン。 */
export const space = {
  1: "var(--space-1)",
  2: "var(--space-2)",
  3: "var(--space-3)",
  4: "var(--space-4)",
  6: "var(--space-6)",
  8: "var(--space-8)",
} as const;

/** 角丸トークン。 */
export const radius = {
  sm: "var(--radius-sm)",
  md: "var(--radius-md)",
} as const;

/** タイポグラフィトークン。 */
export const font = {
  sizeSm: "var(--font-size-sm)",
  sizeBody: "var(--font-size-body)",
  sizeLg: "var(--font-size-lg)",
  sizeXl: "var(--font-size-xl)",
  weightNormal: "var(--font-weight-normal)",
  weightBold: "var(--font-weight-bold)",
} as const;
