# Built in the cloud by `az containerapp up --source .` (D-28) — no local Docker needed.
# Stage 1: static-export the dashboard (D-23); Stage 2: FastAPI serves API + bundle (D-26).

FROM node:22-alpine AS dashboard
WORKDIR /build
RUN npm install -g pnpm@10
COPY dashboard/package.json dashboard/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY dashboard/ ./
RUN pnpm build

FROM python:3.12-slim
WORKDIR /app
COPY api/pyproject.toml ./
COPY api/app ./app
RUN pip install --no-cache-dir .
COPY schema ./schema
COPY --from=dashboard /build/out ./static
ENV SCHEMA_PATH=/app/schema/aggregates.schema.json \
    DASHBOARD_DIST=/app/static
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
