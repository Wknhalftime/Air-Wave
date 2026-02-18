# Deployment Checklist

Use this checklist to ensure a smooth deployment of the library navigation system.

## Pre-Deployment

### Code Quality
- [ ] All tests passing (backend and frontend)
- [ ] No linting errors
- [ ] Code review completed
- [ ] Documentation updated
- [ ] CHANGELOG.md updated with new features

### Database
- [ ] Database migrations created
- [ ] Migrations tested on staging
- [ ] Backup strategy in place
- [ ] Rollback plan documented
- [ ] Indexes verified

### Security
- [ ] Environment variables configured
- [ ] Secrets stored securely (not in code)
- [ ] HTTPS/TLS certificates ready
- [ ] CORS origins configured
- [ ] Rate limiting enabled
- [ ] Security headers configured
- [ ] Dependencies scanned for vulnerabilities

### Performance
- [ ] Load testing completed
- [ ] Cache configuration verified
- [ ] Database query performance tested
- [ ] Frontend bundle size optimized
- [ ] CDN configured (if applicable)

### Monitoring
- [ ] Prometheus metrics configured
- [ ] Grafana dashboards created
- [ ] Alerts configured
- [ ] Log aggregation set up
- [ ] Health check endpoints tested

---

## Deployment Steps

### 1. Prepare Environment

```bash
# Create production environment file
cp .env.example .env.prod

# Edit with production values
nano .env.prod

# Verify configuration
docker-compose -f docker-compose.prod.yml config
```

- [ ] Environment file created
- [ ] All required variables set
- [ ] Configuration validated

### 2. Build Images

```bash
# Build backend image
cd backend
docker build -t airwave-api:1.0.0 .

# Build frontend image (if separate)
cd ../frontend
npm run build
```

- [ ] Backend image built successfully
- [ ] Frontend built successfully
- [ ] Images tagged with version

### 3. Database Setup

```bash
# Start database
docker-compose -f docker-compose.prod.yml up -d db

# Wait for database to be ready
docker-compose -f docker-compose.prod.yml exec db pg_isready -U airwave

# Run migrations
docker-compose -f docker-compose.prod.yml exec api alembic upgrade head

# Verify migration
docker-compose -f docker-compose.prod.yml exec api alembic current
```

- [ ] Database started
- [ ] Migrations applied
- [ ] Migration verified
- [ ] Initial backup created

### 4. Deploy Application

```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Check service status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

- [ ] All services started
- [ ] No errors in logs
- [ ] Health checks passing

### 5. Verify Deployment

```bash
# Test health endpoint
curl https://yourdomain.com/api/v1/health

# Test API endpoints
curl https://yourdomain.com/api/v1/library/artists

# Test frontend
curl https://yourdomain.com/
```

- [ ] Health check returns 200
- [ ] API endpoints responding
- [ ] Frontend loading correctly
- [ ] HTTPS working

### 6. Configure Monitoring

```bash
# Start Prometheus and Grafana
docker-compose -f docker-compose.prod.yml up -d prometheus grafana

# Access Grafana
open https://yourdomain.com:3000

# Import dashboards
# Configure alerts
```

- [ ] Prometheus collecting metrics
- [ ] Grafana dashboards loaded
- [ ] Alerts configured
- [ ] Test alerts working

---

## Post-Deployment

### Immediate Checks (First Hour)

- [ ] Monitor error rates (should be 0%)
- [ ] Check response times (P95 < 200ms)
- [ ] Verify cache hit rates (> 60%)
- [ ] Review application logs
- [ ] Test critical user flows
- [ ] Verify database connections

### First Day Checks

- [ ] Monitor resource usage (CPU, memory, disk)
- [ ] Check for any errors or warnings
- [ ] Verify backups are running
- [ ] Test alert notifications
- [ ] Review performance metrics
- [ ] Gather user feedback

### First Week Checks

- [ ] Analyze performance trends
- [ ] Review slow query logs
- [ ] Check cache effectiveness
- [ ] Monitor disk usage growth
- [ ] Review security logs
- [ ] Plan any optimizations

---

## Rollback Plan

If issues are detected, follow this rollback procedure:

### 1. Stop New Deployment

```bash
# Stop services
docker-compose -f docker-compose.prod.yml stop api
```

- [ ] Services stopped

### 2. Restore Database (if needed)

```bash
# Restore from backup
gunzip -c backup_YYYYMMDD_HHMMSS.sql.gz | \
  docker-compose -f docker-compose.prod.yml exec -T db psql -U airwave airwave

# Rollback migrations (if needed)
docker-compose -f docker-compose.prod.yml exec api alembic downgrade -1
```

- [ ] Database restored
- [ ] Migrations rolled back

### 3. Deploy Previous Version

```bash
# Switch to previous image version
docker-compose -f docker-compose.prod.yml up -d api

# Verify rollback
curl https://yourdomain.com/api/v1/health
```

- [ ] Previous version deployed
- [ ] Services healthy
- [ ] Functionality verified

### 4. Notify Stakeholders

- [ ] Team notified of rollback
- [ ] Users informed (if necessary)
- [ ] Incident documented
- [ ] Post-mortem scheduled

---

## Troubleshooting

### Service Won't Start

**Check:**
- [ ] Docker logs: `docker-compose logs api`
- [ ] Environment variables: `docker-compose exec api env`
- [ ] Database connection: `docker-compose exec db pg_isready`
- [ ] Port conflicts: `netstat -tulpn | grep 8000`

### High Error Rate

**Check:**
- [ ] Application logs for exceptions
- [ ] Database connection pool
- [ ] External service dependencies
- [ ] Recent code changes

### Slow Performance

**Check:**
- [ ] Cache hit rates
- [ ] Database query performance
- [ ] Resource usage (CPU, memory)
- [ ] Network latency

### Database Issues

**Check:**
- [ ] Connection pool settings
- [ ] Query performance
- [ ] Disk space
- [ ] Migration status

---

## Kubernetes Deployment Checklist

If deploying to Kubernetes:

### Pre-Deployment
- [ ] Namespace created
- [ ] ConfigMaps created
- [ ] Secrets created
- [ ] PersistentVolumeClaims created
- [ ] Ingress configured
- [ ] TLS certificates configured

### Deployment
- [ ] Apply namespace: `kubectl apply -f k8s/namespace.yaml`
- [ ] Apply configmaps: `kubectl apply -f k8s/configmap.yaml`
- [ ] Apply secrets: `kubectl apply -f k8s/secrets.yaml`
- [ ] Apply deployment: `kubectl apply -f k8s/deployment.yaml`
- [ ] Apply service: `kubectl apply -f k8s/service.yaml`
- [ ] Apply ingress: `kubectl apply -f k8s/ingress.yaml`

### Verification
- [ ] Pods running: `kubectl get pods -n airwave`
- [ ] Services created: `kubectl get svc -n airwave`
- [ ] Ingress configured: `kubectl get ingress -n airwave`
- [ ] Logs clean: `kubectl logs -f deployment/airwave-api -n airwave`

---

## Sign-Off

### Deployment Team

- [ ] **Developer:** Code deployed and verified
- [ ] **DevOps:** Infrastructure configured and monitored
- [ ] **QA:** Smoke tests passed
- [ ] **Product Owner:** Features verified

### Deployment Details

- **Date:** _______________
- **Version:** _______________
- **Deployed By:** _______________
- **Rollback Plan Tested:** Yes / No
- **Monitoring Verified:** Yes / No

---

## See Also

- [Production Deployment Guide](./production-deployment.md)
- [Monitoring Guide](./monitoring.md)
- [Performance Testing](../testing/performance-testing.md)

