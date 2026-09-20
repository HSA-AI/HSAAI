# HSAAI Frontend — Production-Ready Docker Image
FROM node:22-alpine AS builder
WORKDIR /app
ARG API_GATEWAY_URL=http://api-gateway:8000
ENV API_GATEWAY_URL=$API_GATEWAY_URL
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/api/health || exit 1
EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]
