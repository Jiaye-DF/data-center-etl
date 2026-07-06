# Next.js standalone build — node:24-alpine
FROM node:24-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:24-alpine AS builder
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

FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
