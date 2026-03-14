# Multi-stage build for Angular frontend
FROM node:24-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies using cache mount for npm
RUN --mount=type=cache,target=/root/.npm \
    npm install --legacy-peer-deps

# Copy source code
COPY . .

# Build for production
RUN npm run build

# Production stage with nginx
FROM node:24-slim

# Install nginx and clear default config
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/* && rm -f /etc/nginx/sites-enabled/default

# Clear default nginx assets
RUN rm -rf /usr/share/nginx/html/*

# Copy built app from builder
COPY --from=builder /app/dist/frontend/browser /usr/share/nginx/browser
COPY --from=builder /app/dist/frontend/server /usr/share/nginx/server

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start both Node server and Nginx
CMD ["sh", "-c", "node /usr/share/nginx/server/server.mjs & nginx -g 'daemon off;'"]
