# Frontend Dockerfile - supports both development and production
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install all dependencies (including dev dependencies for development)
RUN npm ci

# Copy source code
COPY . .

# Set build-time environment variables
ARG VITE_API_BASE_URL=http://localhost:8200
ARG VITE_WS_URL=ws://localhost:8200/ws
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_WS_URL=$VITE_WS_URL

# Expose port
EXPOSE 3000

# Default command for development (can be overridden for production)
CMD ["npm", "run", "dev"]