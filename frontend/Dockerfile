# FFCore önyüz imajı. Lint ve testler de bu imajda koşar (host'a Node kurulmaz):
#   docker compose run --rm frontend npm run lint
ARG REGISTRY_PREFIX=
FROM ${REGISTRY_PREFIX}node:20.19.5-alpine
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
