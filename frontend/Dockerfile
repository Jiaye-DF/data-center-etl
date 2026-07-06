# Next.js standalone build — node:24.14.0-alpine(鎖 patch,對齊 docs/Design-Base/00-overview/01-versions.md)
FROM node:24.14.0-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:24.14.0-alpine AS builder
WORKDIR /app
ENV NODE_ENV=production
# NEXT_PUBLIC_* 需於 build 時烘入 bundle,由 compose build args 傳入(.env.example)
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_SSO_URL
ARG NEXT_PUBLIC_SSO_APP_ID
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_SSO_URL=$NEXT_PUBLIC_SSO_URL \
    NEXT_PUBLIC_SSO_APP_ID=$NEXT_PUBLIC_SSO_APP_ID
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24.14.0-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV TZ=Asia/Taipei
RUN apk add --no-cache tzdata \
    && cp /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD wget -qO- http://127.0.0.1:3000/ || exit 1
CMD ["node", "server.js"]
