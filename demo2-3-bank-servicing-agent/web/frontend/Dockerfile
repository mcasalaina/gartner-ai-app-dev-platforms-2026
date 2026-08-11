FROM node:24-alpine AS build

WORKDIR /app

ARG VITE_ENTRA_CLIENT_ID
ARG VITE_ENTRA_TENANT_ID
ARG VITE_API_SCOPE
ARG VITE_API_BASE_URL

ENV VITE_ENTRA_CLIENT_ID=$VITE_ENTRA_CLIENT_ID
ENV VITE_ENTRA_TENANT_ID=$VITE_ENTRA_TENANT_ID
ENV VITE_API_SCOPE=$VITE_API_SCOPE
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN test -n "$VITE_ENTRA_CLIENT_ID" \
    && test -n "$VITE_ENTRA_TENANT_ID" \
    && test -n "$VITE_API_SCOPE" \
    && test -n "$VITE_API_BASE_URL"
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
