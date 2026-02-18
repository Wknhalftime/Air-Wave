# Production Deployment Guide

This guide covers deploying the Airwave library navigation system to production.

## Overview

The library navigation system is designed for production deployment with:
- Docker containerization
- Horizontal scaling support
- Health checks and monitoring
- Graceful shutdown
- Security hardening

---

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+ (for simple deployments)
- Kubernetes 1.24+ (for advanced deployments)
- PostgreSQL 14+ or SQLite 3.35+ (production database)
- Nginx or similar reverse proxy
- SSL/TLS certificates

---

## Docker Deployment

### 1. Create Dockerfile

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==1.7.1

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies (no dev dependencies)
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Create non-root user
RUN useradd -m -u 1000 airwave && chown -R airwave:airwave /app
USER airwave

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/v1/health')"

# Run application
CMD ["uvicorn", "airwave.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 2. Create Docker Compose File

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    image: airwave-api:latest
    container_name: airwave-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://airwave:${DB_PASSWORD}@db:5432/airwave
      - DB_ECHO=false
      - CACHE_DEFAULT_TTL=300
      - LOG_LEVEL=INFO
    volumes:
      - ./data/library:/app/library:ro  # Read-only library files
      - ./data/logs:/app/logs
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - airwave-network
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '1.0'
        reservations:
          memory: 256M
          cpus: '0.5'

  db:
    image: postgres:14-alpine
    container_name: airwave-db
    restart: unless-stopped
    environment:
      - POSTGRES_USER=airwave
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=airwave
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./backups:/backups
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U airwave"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - airwave-network
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'

  nginx:
    image: nginx:alpine
    container_name: airwave-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"


```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: airwave-api
  namespace: airwave
spec:
  replicas: 3
  selector:
    matchLabels:
      app: airwave-api
  template:
    metadata:
      labels:
        app: airwave-api
    spec:
      containers:
      - name: api
        image: airwave-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          value: "postgresql://airwave:$(DB_PASSWORD)@postgres:5432/airwave"
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: airwave-secrets
              key: db-password
        envFrom:
        - configMapRef:
            name: airwave-config
        resources:
          requests:
            memory: "256Mi"
            cpu: "500m"
          limits:
            memory: "512Mi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

### 5. Create Service

Create `k8s/service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: airwave-api
  namespace: airwave
spec:
  selector:
    app: airwave-api
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: ClusterIP
```

### 6. Create Ingress

Create `k8s/ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: airwave-ingress
  namespace: airwave
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "10"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - yourdomain.com
    secretName: airwave-tls
  rules:
  - host: yourdomain.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: airwave-api
            port:
              number: 8000
```

### 7. Deploy to Kubernetes

```bash
# Apply all configurations
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Check deployment status
kubectl get pods -n airwave
kubectl get svc -n airwave
kubectl get ingress -n airwave

# View logs
kubectl logs -f deployment/airwave-api -n airwave

# Scale deployment
kubectl scale deployment airwave-api --replicas=5 -n airwave
```

---

## Health Checks

### Add Health Check Endpoint

Update `backend/src/airwave/api/routers/system.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from airwave.core.db import get_db
from airwave.core.cache import cache

router = APIRouter()

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint for load balancers"""

    # Check database connection
    try:
        await db.execute("SELECT 1")
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "down",
            "error": str(e)
        }

    # Check cache
    cache_status = "ok" if cache else "disabled"

    return {
        "status": "healthy",
        "database": "up",
        "cache": cache_status
    }

@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness check for Kubernetes"""

    # Check if application is ready to serve traffic
    try:
        await db.execute("SELECT 1")
        return {"status": "ready"}
    except Exception:
        return {"status": "not ready"}, 503
```

---

## Database Migrations

### Production Migration Strategy

```bash
# 1. Backup database before migration
docker-compose exec db pg_dump -U airwave airwave > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Run migrations
docker-compose exec api alembic upgrade head

# 3. Verify migration
docker-compose exec api alembic current

# 4. If migration fails, rollback
docker-compose exec api alembic downgrade -1

# 5. Restore from backup if needed
docker-compose exec -T db psql -U airwave airwave < backup_20240218_120000.sql
```

---

## Monitoring Setup

### Prometheus Metrics

Add Prometheus metrics endpoint:

```python
# backend/src/airwave/api/main.py
from prometheus_client import Counter, Histogram, generate_latest
from fastapi import Response

# Metrics
request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'])

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type="text/plain")
```

### Prometheus Configuration

Create `prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'airwave-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
```

---

## Logging Configuration

### Structured Logging

Update logging configuration:

```python
# backend/src/airwave/core/logging.py
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging"""

    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)

# Configure logging
def setup_logging(log_level: str = "INFO", log_file: str = None):
    """Setup structured logging"""

    formatter = JSONFormatter()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # File handler (if specified)
    handlers = [console_handler]
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level),
        handlers=handlers
    )
```

---

## Backup and Recovery

### Automated Backups

Create `scripts/backup.sh`:

```bash
#!/bin/bash
# Automated database backup script

BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/airwave_backup_$TIMESTAMP.sql"
RETENTION_DAYS=7

# Create backup
docker-compose exec -T db pg_dump -U airwave airwave > "$BACKUP_FILE"

# Compress backup
gzip "$BACKUP_FILE"

# Remove old backups
find "$BACKUP_DIR" -name "airwave_backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: ${BACKUP_FILE}.gz"
```

### Restore Procedure

```bash
# 1. Stop application
docker-compose stop api

# 2. Restore database
gunzip -c backup_20240218_120000.sql.gz | \
  docker-compose exec -T db psql -U airwave airwave

# 3. Run migrations (if needed)
docker-compose exec api alembic upgrade head

# 4. Clear cache
curl -X POST http://localhost:8000/api/v1/system/cache/clear

# 5. Start application
docker-compose start api
```

---

## Security Hardening

### Security Checklist

- ✅ Use HTTPS/TLS for all connections
- ✅ Set strong database passwords
- ✅ Restrict cache management endpoints to internal IPs
- ✅ Enable rate limiting on API endpoints
- ✅ Use non-root user in Docker containers
- ✅ Keep dependencies up to date
- ✅ Enable CORS only for trusted origins
- ✅ Use environment variables for secrets
- ✅ Implement request size limits
- ✅ Enable security headers (HSTS, X-Frame-Options, etc.)
- ✅ Regular security audits
- ✅ Monitor for suspicious activity

### Environment Variables

Never commit these to version control:

```bash
# .env.prod (add to .gitignore)
DB_PASSWORD=<strong-password>
API_SECRET_KEY=<random-secret-key>
JWT_SECRET=<jwt-secret>
```

---

## Troubleshooting

### Common Issues

**Issue: Container fails to start**
```bash
# Check logs
docker-compose logs api

# Check health status
docker-compose ps
```

**Issue: Database connection fails**
```bash
# Verify database is running
docker-compose exec db pg_isready -U airwave

# Check connection string
docker-compose exec api env | grep DATABASE_URL
```

**Issue: High memory usage**
```bash
# Check container stats
docker stats

# Reduce cache size or add memory limits
```

---

## See Also

- [Monitoring Guide](./monitoring.md) - Detailed monitoring setup
- [Performance Testing](../testing/performance-testing.md) - Load testing
- [Architecture](../architecture/caching.md) - System architecture

