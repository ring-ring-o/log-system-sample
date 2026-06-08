# FlowNote Web — マルチステージビルド(Next.js standalone・軽量ランタイム)。
# next.config の output: "standalone" を前提とする。

FROM node:22-bookworm-slim AS builder
RUN corepack enable
WORKDIR /app
# ワークスペース解決のためのマニフェストを先に取り込み、依存をキャッシュする。
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml* ./
COPY packages/observability-web ./packages/observability-web
COPY apps/web ./apps/web
RUN pnpm install --frozen-lockfile || pnpm install
RUN pnpm --filter web build
# public は任意。未作成でもランタイムの COPY が失敗しないよう空ディレクトリを保証する。
RUN mkdir -p apps/web/public

FROM node:22-bookworm-slim AS runtime
# node イメージは UID 1000 の非 root ユーザー `node` を標準同梱するため、それを再利用する
# (独自に useradd --uid 1000 すると UID 重複で exit code 4 となる)。
WORKDIR /app
ENV NODE_ENV=production
# standalone 出力(サーバ + 必要な node_modules)と静的アセットのみを持ち込む。
COPY --from=builder --chown=node:node /app/apps/web/.next/standalone ./
COPY --from=builder --chown=node:node /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=node:node /app/apps/web/public ./apps/web/public
USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
