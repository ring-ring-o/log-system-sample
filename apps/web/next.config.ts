import type { NextConfig } from "next";

/**
 * Next.js 設定。
 *
 * - `output: "standalone"` で軽量なランタイム成果物を生成する(マルチステージビルド用)。
 * - 共有可観測性パッケージ(TS ソース提供)を Next 側で変換する。
 */
const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ["@flownote/observability-web"],
};

export default nextConfig;
