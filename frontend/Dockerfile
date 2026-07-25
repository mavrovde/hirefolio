# Multi-stage build for Angular frontend
FROM node:26-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies using cache mount for npm
RUN --mount=type=cache,target=/root/.npm \
    npm install --legacy-peer-deps

# Copy source code
COPY . .

# Build the public SSR app (and the shared library it depends on)
RUN npm run build:shared && npm run build:public

# Production stage with nginx
FROM node:26-slim

# Install nginx and clear default config
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/* && rm -f /etc/nginx/sites-enabled/default

# Clear default nginx assets
RUN rm -rf /usr/share/nginx/html/*

# Copy built public app from builder
COPY --from=builder /app/dist/public/browser /usr/share/nginx/browser
COPY --from=builder /app/dist/public/server /usr/share/nginx/server

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start both Node server and Nginx
CMD ["sh", "-c", "node /usr/share/nginx/server/server.mjs & nginx -g 'daemon off;'"]
