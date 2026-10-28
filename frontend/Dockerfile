# FFCore önyüz imajı. Lint ve testler de bu imajda koşar (host'a Node kurulmaz):
#   docker compose run --rm frontend npm run lint
ARG REGISTRY_PREFIX=
FROM ${REGISTRY_PREFIX}node:20.19.5-alpine
# Backend origin for the /api/v1 rewrite (C6); Next.js fixes rewrites at build time. Required:
# the build fails without it (lib/backend.ts). Compose passes http://backend:8000.
ARG FFCORE_BACKEND_URL
ENV FFCORE_BACKEND_URL=${FFCORE_BACKEND_URL}
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
