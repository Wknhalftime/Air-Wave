# Deployment Documentation

This directory contains comprehensive deployment and operations documentation for the Airwave library navigation system.

## Quick Links

- **[Production Deployment Guide](./production-deployment.md)** - Complete deployment instructions
- **[Monitoring Guide](./monitoring.md)** - Monitoring and observability setup
- **[Deployment Checklist](./deployment-checklist.md)** - Step-by-step deployment checklist

---

## Documentation Overview

### 1. Production Deployment Guide

**File:** `production-deployment.md`

**Contents:**
- Docker deployment with Docker Compose
- Kubernetes deployment with manifests
- Nginx reverse proxy configuration
- Health check endpoints
- Database migration strategy
- Backup and recovery procedures
- Security hardening checklist
- Troubleshooting guide

**Use this when:**
- Setting up a new production environment
- Configuring infrastructure
- Planning deployment architecture

---

### 2. Monitoring Guide

**File:** `monitoring.md`

**Contents:**
- Prometheus metrics collection
- Grafana dashboard configuration
- Alert rules and AlertManager setup
- Structured logging configuration
- Application Performance Monitoring (APM)
- Monitoring checklist (daily, weekly, monthly)

**Use this when:**
- Setting up monitoring infrastructure
- Creating dashboards and alerts
- Troubleshooting performance issues
- Planning capacity

---

### 3. Deployment Checklist

**File:** `deployment-checklist.md`

**Contents:**
- Pre-deployment checklist
- Step-by-step deployment procedure
- Post-deployment verification
- Rollback plan
- Troubleshooting guide
- Sign-off template

**Use this when:**
- Deploying to production
- Performing updates or releases
- Training new team members
- Documenting deployments

---

## Quick Start

### For First-Time Deployment

1. **Read the Production Deployment Guide**
   - Understand the architecture
   - Choose deployment method (Docker or Kubernetes)
   - Prepare infrastructure

2. **Follow the Deployment Checklist**
   - Complete pre-deployment tasks
   - Execute deployment steps
   - Verify deployment

3. **Set Up Monitoring**
   - Configure Prometheus and Grafana
   - Create dashboards
   - Set up alerts

### For Updates and Releases

1. **Review the Deployment Checklist**
   - Ensure all pre-deployment tasks are complete
   - Verify rollback plan

2. **Execute Deployment**
   - Follow deployment steps
   - Monitor during deployment

3. **Post-Deployment Verification**
   - Check health endpoints
   - Verify metrics
   - Monitor for issues

---

## Deployment Methods

### Docker Compose (Recommended for Small Deployments)

**Pros:**
- Simple setup
- Easy to understand
- Good for single-server deployments
- Quick to get started

**Cons:**
- Limited scaling options
- No built-in high availability
- Manual load balancing

**Best for:**
- Development environments
- Small production deployments (< 100 concurrent users)
- Single-server setups

**See:** [Production Deployment Guide - Docker Deployment](./production-deployment.md#docker-deployment)

---

### Kubernetes (Recommended for Large Deployments)

**Pros:**
- Horizontal scaling
- Built-in high availability
- Automatic load balancing
- Self-healing
- Rolling updates

**Cons:**
- More complex setup
- Requires Kubernetes knowledge
- Higher resource overhead

**Best for:**
- Large production deployments (> 100 concurrent users)
- Multi-server setups
- High availability requirements

**See:** [Production Deployment Guide - Kubernetes Deployment](./production-deployment.md#kubernetes-deployment)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Load Balancer                        │
│                      (Nginx / Ingress)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
        ┌───────▼────────┐         ┌───────▼────────┐
        │   API Server   │         │   API Server   │
        │   (Instance 1) │         │   (Instance 2) │
        └───────┬────────┘         └───────┬────────┘
                │                           │
                └─────────────┬─────────────┘
                              │
                    ┌─────────▼─────────┐
                    │    PostgreSQL     │
                    │    (Database)     │
                    └───────────────────┘

        ┌─────────────────────────────────────────┐
        │          Monitoring Stack               │
        ├─────────────────────────────────────────┤
        │  Prometheus  │  Grafana  │ AlertManager │
        └─────────────────────────────────────────┘
```

---

## Environment Variables

### Required Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@host:5432/dbname
DB_PASSWORD=<secure-password>

# API
API_SECRET_KEY=<random-secret-key>
API_CORS_ORIGINS=https://yourdomain.com

# Cache
CACHE_DEFAULT_TTL=300

# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/airwave.log
```

### Optional Variables

```bash
# Database
DB_ECHO=false  # Enable query logging (development only)

# Monitoring
SENTRY_DSN=https://...@sentry.io/...  # Error tracking
PROMETHEUS_ENABLED=true

# Performance
WORKERS=4  # Number of Uvicorn workers
```

---

## Security Considerations

### Essential Security Measures

1. **HTTPS/TLS**
   - Use valid SSL certificates
   - Redirect HTTP to HTTPS
   - Enable HSTS headers

2. **Secrets Management**
   - Never commit secrets to version control
   - Use environment variables or secret managers
   - Rotate secrets regularly

3. **Access Control**
   - Restrict cache management endpoints
   - Use IP whitelisting for admin endpoints
   - Implement rate limiting

4. **Database Security**
   - Use strong passwords
   - Limit network access
   - Enable SSL connections
   - Regular backups

5. **Container Security**
   - Run as non-root user
   - Use minimal base images
   - Keep dependencies updated
   - Scan for vulnerabilities

**See:** [Production Deployment Guide - Security Hardening](./production-deployment.md#security-hardening)

---

## Monitoring and Alerts

### Key Metrics to Monitor

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Error Rate | < 0.1% | > 1% |
| P95 Response Time | < 200ms | > 500ms |
| Cache Hit Rate | > 60% | < 40% |
| Memory Usage | < 70% | > 85% |
| CPU Usage | < 70% | > 85% |
| Disk Usage | < 80% | > 90% |

### Alert Severity Levels

- **Critical** - Immediate action required (service down, database unavailable)
- **Warning** - Action needed soon (high error rate, slow responses)
- **Info** - Informational (deployment completed, cache cleared)

**See:** [Monitoring Guide - Alert Configuration](./monitoring.md#alert-configuration)

---

## Backup and Recovery

### Backup Strategy

- **Frequency:** Daily automated backups
- **Retention:** 7 days of daily backups, 4 weeks of weekly backups
- **Storage:** Off-site backup storage
- **Testing:** Monthly restore tests

### Recovery Time Objectives

- **RTO (Recovery Time Objective):** < 1 hour
- **RPO (Recovery Point Objective):** < 24 hours

**See:** [Production Deployment Guide - Backup and Recovery](./production-deployment.md#backup-and-recovery)

---

## Support and Troubleshooting

### Common Issues

1. **Service won't start** → Check logs and environment variables
2. **Database connection fails** → Verify connection string and database status
3. **High error rate** → Check application logs and recent changes
4. **Slow performance** → Review cache hit rates and query performance

**See:** [Deployment Checklist - Troubleshooting](./deployment-checklist.md#troubleshooting)

---

## Additional Resources

- [API Documentation](../api/library-navigation.md)
- [Architecture Documentation](../architecture/caching.md)
- [Performance Testing Guide](../testing/performance-testing.md)
- [Developer Guide](../developer-guide/extending-navigation.md)

---

## Getting Help

- **Documentation Issues:** Open an issue in the repository
- **Deployment Questions:** Contact the DevOps team
- **Production Incidents:** Follow the incident response procedure

