# Monitoring and Observability Guide

This guide covers monitoring, logging, and observability for the Airwave library navigation system.

## Overview

Comprehensive monitoring ensures:
- Early detection of issues
- Performance optimization insights
- Capacity planning data
- Incident response support

**Monitoring Stack:**
- **Prometheus** - Metrics collection
- **Grafana** - Visualization and dashboards
- **Loki** - Log aggregation (optional)
- **AlertManager** - Alert routing and management

---

## Metrics Collection

### Prometheus Setup

#### 1. Add Prometheus Client

Update `backend/pyproject.toml`:

```toml
[tool.poetry.dependencies]
prometheus-client = "^0.19.0"
```

#### 2. Create Metrics Module

Create `backend/src/airwave/core/metrics.py`:

```python
"""Prometheus metrics for monitoring"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from functools import wraps
import time

# Request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# Cache metrics
cache_hits_total = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['endpoint']
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['endpoint']
)

cache_size = Gauge(
    'cache_size',
    'Current number of items in cache'
)

# Database metrics
db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

db_connections_active = Gauge(
    'db_connections_active',
    'Number of active database connections'
)

# Application metrics
app_info = Gauge(
    'app_info',
    'Application information',
    ['version', 'environment']
)


def track_request_metrics(endpoint: str):
    """Decorator to track request metrics"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = 200
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = 500
                raise
            finally:
                duration = time.time() - start_time
                http_requests_total.labels(
                    method='GET',
                    endpoint=endpoint,
                    status=status
                ).inc()
                http_request_duration_seconds.labels(
                    method='GET',
                    endpoint=endpoint
                ).observe(duration)
        
        return wrapper
    return decorator
```

#### 3. Add Metrics Endpoint

Update `backend/src/airwave/api/main.py`:

```python
from fastapi import FastAPI, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from airwave.core.metrics import app_info

app = FastAPI()

# Set application info
app_info.labels(version="1.0.0", environment="production").set(1)

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

#### 4. Update Cache to Track Metrics

Update `backend/src/airwave/core/cache.py`:

```python
from airwave.core.metrics import cache_hits_total, cache_misses_total, cache_size

class SimpleCache:
    def get(self, key: str):
        """Get value from cache"""
        entry = self._cache.get(key)
        
        if entry and not self._is_expired(entry):
            cache_hits_total.labels(endpoint=key.split(':')[0]).inc()
            return entry.value
        
        cache_misses_total.labels(endpoint=key.split(':')[0]).inc()
        return None
    
    def set(self, key: str, value: Any, ttl: int = None):
        """Set value in cache"""
        # ... existing code ...
        cache_size.set(len(self._cache))
```

#### 5. Prometheus Configuration

Create `prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'airwave-prod'
    environment: 'production'

# Alertmanager configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

# Load rules
rule_files:
  - 'alerts.yml'

# Scrape configurations
scrape_configs:
  # Airwave API
  - job_name: 'airwave-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s

  # Prometheus itself
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Node exporter (system metrics)
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
```

---

## Grafana Dashboards

### 1. Deploy Grafana

Add to `docker-compose.prod.yml`:

```yaml
services:
  grafana:
    image: grafana/grafana:latest
    container_name: airwave-grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
    networks:
      - airwave-network

  prometheus:
    image: prom/prometheus:latest
    container_name: airwave-prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus/alerts.yml:/etc/prometheus/alerts.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
    networks:
      - airwave-network

volumes:
  grafana-data:
  prometheus-data:
```

### 2. Configure Datasource

Create `grafana/datasources/prometheus.yml`:

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

### 3. Create Dashboard

Create `grafana/dashboards/airwave-overview.json`:

```json
{
  "dashboard": {
    "title": "Airwave Library Navigation",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Response Time (P95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "targets": [
          {
            "expr": "rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))"
          }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[5m])"
          }
        ]
      }
    ]
  }
}
```

---

## Alert Configuration

### 1. Create Alert Rules

Create `prometheus/alerts.yml`:

```yaml
groups:
  - name: airwave_alerts
    interval: 30s
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: |
          rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors/sec"

      # Slow response time
      - alert: SlowResponseTime
        expr: |
          histogram_quantile(0.95, 
            rate(http_request_duration_seconds_bucket[5m])
          ) > 1.0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Slow response time"
          description: "P95 response time is {{ $value }}s"

      # Low cache hit rate
      - alert: LowCacheHitRate
        expr: |
          rate(cache_hits_total[5m]) / 
          (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m])) < 0.5
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Low cache hit rate"
          description: "Cache hit rate is {{ $value | humanizePercentage }}"

      # High memory usage
      - alert: HighMemoryUsage
        expr: |
          (container_memory_usage_bytes{name="airwave-api"} / 
           container_spec_memory_limit_bytes{name="airwave-api"}) > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value | humanizePercentage }}"

      # Database connection issues
      - alert: DatabaseConnectionIssues
        expr: |
          db_connections_active == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "No active database connections"
          description: "Database may be down or unreachable"

      # Service down
      - alert: ServiceDown
        expr: |
          up{job="airwave-api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Airwave API is down"
          description: "API service is not responding"
```

### 2. Configure AlertManager

Create `alertmanager/alertmanager.yml`:

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'cluster']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical'
      continue: true
    - match:
        severity: warning
      receiver: 'warning'

receivers:
  - name: 'default'
    email_configs:
      - to: 'team@example.com'
        from: 'alerts@example.com'
        smarthost: 'smtp.example.com:587'
        auth_username: 'alerts@example.com'
        auth_password: '${SMTP_PASSWORD}'

  - name: 'critical'
    email_configs:
      - to: 'oncall@example.com'
        from: 'alerts@example.com'
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_URL}'
        channel: '#alerts-critical'
        title: 'Critical Alert: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

  - name: 'warning'
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_URL}'
        channel: '#alerts-warning'
        title: 'Warning: {{ .GroupLabels.alertname }}'
```

---

## Logging

### 1. Structured Logging

Already covered in production-deployment.md. Key points:

- Use JSON format for structured logs
- Include timestamp, level, logger, message, context
- Log to stdout for container environments
- Use log aggregation (Loki, ELK, etc.)

### 2. Log Levels

```python
# Production logging levels
CRITICAL - System is unusable (database down, critical service failure)
ERROR    - Error occurred but system continues (failed request, exception)
WARNING  - Warning condition (slow query, high memory, deprecated API)
INFO     - Normal operation (request completed, cache cleared)
DEBUG    - Detailed information (query details, cache operations)
```

### 3. What to Log

**DO Log:**
- Request/response (method, path, status, duration)
- Errors and exceptions (with stack traces)
- Performance metrics (slow queries, cache misses)
- Security events (authentication failures, rate limit hits)
- System events (startup, shutdown, configuration changes)

**DON'T Log:**
- Sensitive data (passwords, tokens, personal information)
- Full request/response bodies (unless debugging)
- Excessive debug information in production

---

## Application Performance Monitoring (APM)

### Optional: Add Sentry for Error Tracking

```python
# backend/src/airwave/api/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

sentry_sdk.init(
    dsn="https://your-sentry-dsn@sentry.io/project-id",
    integrations=[
        FastApiIntegration(),
        SqlalchemyIntegration(),
    ],
    traces_sample_rate=0.1,  # 10% of transactions
    environment="production",
)
```

---

## Monitoring Checklist

### Daily Checks
- ✅ Check error rate (should be < 0.1%)
- ✅ Check response times (P95 < 200ms)
- ✅ Check cache hit rate (> 60%)
- ✅ Review critical alerts

### Weekly Checks
- ✅ Review performance trends
- ✅ Check disk usage
- ✅ Review slow queries
- ✅ Update dependencies

### Monthly Checks
- ✅ Capacity planning review
- ✅ Security audit
- ✅ Backup verification
- ✅ Disaster recovery test

---

## See Also

- [Production Deployment](./production-deployment.md) - Deployment guide
- [Performance Testing](../testing/performance-testing.md) - Load testing
- [Architecture](../architecture/caching.md) - System architecture

