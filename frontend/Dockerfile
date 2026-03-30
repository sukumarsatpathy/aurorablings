# Build stage
FROM node:20-alpine AS build
WORKDIR /app

# 1. Copy the lockfiles from the frontend subfolder
COPY frontend/package*.json ./

# 2. This will now work because the files are in the WORKDIR (/app)
RUN npm ci

# 3. Copy the rest of the frontend source code
COPY frontend/ ./

# 4. Build the project
RUN npm run build

# Production stage
FROM nginx:stable-alpine AS runner

# 5. Copy custom nginx config (This was also causing an error)
# Note: We use the root path because the context in deploy.yml is "."
COPY deploy/nginx/frontend.conf /etc/nginx/conf.d/default.conf

# 6. Copy build artifacts from the build stage
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=15s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]