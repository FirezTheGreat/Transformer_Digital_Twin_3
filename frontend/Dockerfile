# syntax=docker/dockerfile:1
# Multi-stage build for frontend
FROM node:20-alpine AS builder

WORKDIR /app

# Copy fixtures to match relative import path (../../../fixtures/mockFactBundle.json)
COPY fixtures /app/fixtures

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install

COPY frontend/ ./
RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/frontend/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
