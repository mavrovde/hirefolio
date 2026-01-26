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

# Copy built app from builder
COPY --from=builder /app/dist/frontend/browser /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
