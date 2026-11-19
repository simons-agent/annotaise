# syntax=docker/dockerfile:1
# Deploy-only frontend image for the PrivDev instances.
# Unlike the upstream frontend/Dockerfile (which installs and builds at
# container start via run.sh), this installs from the lockfile and builds at
# image build time; the container only runs `next start`.
# NEXT_PUBLIC_* values are inlined by `next build`, so they are build args:
# changing them requires a rebuild (see README "Rebuild").

FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG NEXT_PUBLIC_BASE_PATH
ARG NEXT_PUBLIC_API_BASE_URL
RUN test -n "$NEXT_PUBLIC_BASE_PATH" && test -n "$NEXT_PUBLIC_API_BASE_URL" \
 && npm run build

FROM node:22-alpine
WORKDIR /app
# next start re-reads next.config.ts, whose basePath comes from this variable.
ARG NEXT_PUBLIC_BASE_PATH
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 \
    NEXT_PUBLIC_BASE_PATH=$NEXT_PUBLIC_BASE_PATH
# Keep devDependencies: `next start` loads next.config.ts and would otherwise
# try to install TypeScript from the network at startup.
COPY --from=build /app ./
EXPOSE 3000
CMD ["node_modules/.bin/next", "start", "-p", "3000"]
