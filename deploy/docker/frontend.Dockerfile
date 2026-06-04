# Frontend Dockerfile for Next.js App Router standalone runtime.

FROM node:22-alpine AS build

ARG NEXT_PUBLIC_API_BASE_URL=""
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app/frontend

RUN corepack enable && corepack prepare pnpm@latest --activate

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --ignore-scripts

COPY frontend/. ./
COPY docs /app/docs

RUN pnpm build

FROM node:22-alpine AS runtime

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

WORKDIR /app

RUN addgroup -S nextjs && adduser -S nextjs -G nextjs

COPY --from=build --chown=nextjs:nextjs /app/frontend/.next/standalone ./
COPY --from=build --chown=nextjs:nextjs /app/frontend/.next/static ./.next/static
COPY --from=build --chown=nextjs:nextjs /app/frontend/public ./public
COPY --from=build --chown=nextjs:nextjs /app/docs ./docs

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
