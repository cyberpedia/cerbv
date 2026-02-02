# Cerberus CTF - Web Node.js Challenge Template
# Supports: Node.js 20 LTS, Express, common web vulnerabilities

FROM node:20-alpine

# Security: Run as non-root
RUN addgroup -g 1000 -S ctf && adduser -u 1000 -S ctf -G ctf

# Install security updates
RUN apk update && apk upgrade && apk add --no-cache \
    dumb-init \
    curl \
    && rm -rf /var/cache/apk/*

# Create app directory
WORKDIR /app

# Copy package files first (for better caching)
COPY --chown=ctf:ctf package*.json ./

# Install dependencies
RUN npm ci --only=production --no-audit --no-fund \
    && npm cache clean --force

# Copy application code
COPY --chown=ctf:ctf . .

# Set permissions
RUN chmod -R 755 /app \
    && chmod -R 777 /app/uploads 2>/dev/null || true \
    && chmod -R 777 /app/tmp 2>/dev/null || true \
    && chmod -R 777 /app/logs 2>/dev/null || true

# Security: Remove unnecessary tools
RUN apk del curl 2>/dev/null || true

# Create tmpfs directories
RUN mkdir -p /tmp/uploads /tmp/sessions \
    && chown ctf:ctf /tmp/uploads /tmp/sessions

# Switch to non-root user
USER ctf

# Environment variables
ENV NODE_ENV=production \
    PORT=3000 \
    TMPDIR=/tmp

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/health', (r) => r.statusCode === 200 ? process.exit(0) : process.exit(1))"

EXPOSE 3000

# Use dumb-init for proper signal handling
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "server.js"]