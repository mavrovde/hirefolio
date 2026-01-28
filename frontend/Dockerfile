# Multi-stage build for Angular frontend
FROM node:24-alpine AS builder

WORKDIR /app


# Upgrade npm to latest
RUN npm install -g npm@latest

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Copy source code
COPY . .

# Build for production
RUN npm run build

# Production stage with nginx
FROM nginx:alpine

# Install latest npm (requires nodejs)
RUN apk add --no-cache nodejs npm && npm install -g npm@latest

# Clear default nginx assets
RUN rm -rf /usr/share/nginx/html/*

# Copy built app from builder
COPY --from=builder /app/dist/frontend/browser /usr/share/nginx/html
COPY --from=builder /app/dist/frontend/server /usr/share/nginx/server

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start both Node server and Nginx
CMD ["sh", "-c", "node /usr/share/nginx/server/server.mjs & nginx -g 'daemon off;'"]
