# Cerberus CTF Platform - Installation Guide

## Prerequisites

### Hardware Requirements
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| Memory | 8 GB | 16+ GB |
| Storage | 50 GB SSD | 200+ GB SSD |
| Network | 100 Mbps | 1 Gbps |

### Software Requirements
- Docker 24+ with Docker Compose v2
- Kubernetes 1.28+ (for production)
- PostgreSQL 16+
- Redis 7+
- Python 3.11+
- Node.js 20+

## Quick Start (Docker Compose)

### 1. Clone Repository
```bash
git clone https://github.com/cerberus-ctf/cerberus.git
cd cerberus
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Start Services
```bash
docker compose up -d
```

### 4. Initialize Database
```bash
docker compose exec backend python -m app.core.database init
```

### 5. Access Platform
- Web UI: http://localhost:3000
- API: http://localhost:8000
- Admin: http://localhost:8000/admin

## Production Deployment (Kubernetes)

### 1. Install Prerequisites
```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

# Install helm
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install kustomize
curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash
```

### 2. Configure Secrets
```bash
# Create namespace
kubectl apply -f k8s/base/namespace.yaml

# Create secrets (use SealedSecrets in production)
kubectl apply -f k8s/base/secret.yaml

# Create configmaps
kubectl apply -f k8s/base/configmap.yaml
```

### 3. Deploy Platform
```bash
# Deploy to staging
kubectl apply -k k8s/overlays/staging

# Deploy to production
kubectl apply -k k8s/overlays/production
```

### 4. Verify Deployment
```bash
kubectl rollout status deployment/cerberus-backend -n cerberus
kubectl get pods -n cerberus
```

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | Required |
| `SECRET_KEY` | Application secret key | Required |
| `DOMAIN` | Platform domain | localhost |
| `ADMIN_EMAIL` | Admin email for Let's Encrypt | Required |
| `LOG_LEVEL` | Logging level | info |

### Privacy Mode Settings

| Mode | Description |
|------|-------------|
| `full` | All data visible (default) |
| `anonymous` | Team names masked |
| `stealth` | Solves hidden |
| `delayed` | Scoreboard delayed (configurable minutes) |

## SSL/TLS Configuration

### Let's Encrypt (Automatic)
```yaml
# In traefik/dynamic.yaml
certificatesResolvers:
  letsencrypt:
    acme:
      email: admin@example.com
      storage: /letsencrypt/acme.json
      httpChallenge:
        entryPoint: web
```

### Custom Certificates
```bash
# Create secret from certificate
kubectl create secret tls cert-secret \
  --cert=path/to/cert.pem \
  --key=path/to/key.pem \
  -n cerberus
```

## Database Setup

### PostgreSQL Initialization
```sql
-- Create database
CREATE DATABASE cerberus;

-- Create user
CREATE USER cerberus WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE cerberus TO cerberus;

-- Grant schema permissions
\c cerberus
GRANT ALL ON SCHEMA public TO cerberus;
```

### Redis Configuration
```conf
maxmemory 1gb
maxmemory-policy allkeys-lru
appendonly yes
appendfsync everysec
```

## Verification Checklist

- [ ] All services running: `docker compose ps` or `kubectl get pods`
- [ ] Health check passing: `curl http://localhost:8000/health`
- [ ] Web UI accessible: `http://localhost:3000`
- [ ] API docs available: `http://localhost:8000/docs`
- [ ] Admin panel accessible: `http://localhost:8000/admin`

## Troubleshooting

### Services Not Starting
```bash
# Check logs
docker compose logs -f

# Check resource usage
docker stats
```

### Database Connection Issues
```bash
# Test connection
docker compose exec backend python -c "from app.core.database import test_connection; test_connection()"

# Check PostgreSQL status
docker compose exec postgres pg_isready -U cerberus
```

### DNS Resolution Issues
```bash
# Check Traefik router configuration
kubectl logs -n kube-system deployment/traefik -f
```

## Next Steps

1. [Configure authentication](security.md)
2. [Set up challenges](challenge-creation.md)
3. [Configure monitoring](monitoring-alerts.md)
4. [Set up backups](backup-restore.md)
