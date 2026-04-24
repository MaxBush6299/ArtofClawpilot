FROM node:20-bookworm-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends git python3 ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY . .

ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1
ENV HOSTED_RUNNER_COMMAND python3 -m orchestrator.main --repo-root "$REPO_WORKSPACE"

CMD ["node", "scripts/hosted-bootstrap.mjs"]
