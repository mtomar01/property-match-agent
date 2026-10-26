# Tispi's beta image (D100): the built React app and the Python server, with the private snapshot copied in at
# build time from data/private/deploy/ (ignored by git, so the listings go into Mike's private Fly image and
# nowhere else). Build and deploy with flyctl; see docs/deploy.md.

FROM node:20-alpine AS app
WORKDIR /build/app
COPY app/package.json app/package-lock.json ./
RUN npm ci
COPY app/ ./
RUN npm run build

FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /srv
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
COPY --from=app /build/app/dist ./app/dist
ENV PM_HOST=0.0.0.0 \
    PORT=8765 \
    PM_SNAPSHOT=/srv/data/private/deploy/snapshot.jsonl \
    TISPI_IDLE_MINUTES=15 \
    TISPI_TURNS_PER_VISITOR=30 \
    TISPI_TURNS_PER_DAY=150
EXPOSE 8765
CMD ["uv", "run", "--no-sync", "python", "-m", "api.server"]
