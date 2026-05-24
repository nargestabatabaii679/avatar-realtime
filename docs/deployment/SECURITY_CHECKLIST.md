# Production Security Checklist

## Authentication & Authorization

- [ ] **SECRET_KEY** is cryptographically random (minimum 64 characters)
- [ ] JWT algorithm set to `RS256` (asymmetric) in production, not `HS256`
- [ ] Access tokens expire in ≤ 30 minutes
- [ ] Refresh tokens are stored hashed in database
- [ ] Refresh tokens are single-use (rotate on each refresh)
- [ ] Logout invalidates refresh token in Redis blacklist
- [ ] Failed login attempts trigger rate limiting (5 attempts → 15-minute lockout)
- [ ] Admin accounts require MFA (TOTP via Google Authenticator)
- [ ] API keys are hashed with bcrypt before storage (never stored plaintext)
- [ ] OAuth2 redirect URIs are whitelisted exactly
- [ ] Password reset tokens expire in 1 hour and are single-use
- [ ] Email verification required before account activation

## Network Security

- [ ] All traffic via HTTPS (TLS 1.2+ only, disable TLS 1.0/1.1)
- [ ] HSTS header enabled with 1-year max-age + preload
- [ ] SSL certificate is valid and auto-renewed (Let's Encrypt or commercial)
- [ ] Nginx configured with strong cipher suites (A+ SSL Labs rating)
- [ ] Backend API not directly accessible from internet (only via Nginx)
- [ ] Database port (5432) not exposed to internet
- [ ] Redis port (6379) not exposed to internet
- [ ] MinIO admin console (9001) behind VPN or IP whitelist
- [ ] Flower (Celery monitor) behind authentication
- [ ] Prometheus/Grafana behind authentication
- [ ] Rate limiting enabled at Nginx and application level
- [ ] IP whitelisting for admin endpoints

## CORS Configuration

- [ ] CORS origins restricted to specific production domains
- [ ] `Access-Control-Allow-Origin: *` NEVER used in production
- [ ] Credentials flag properly set
- [ ] Preflight caching configured

## Input Validation & Injection Prevention

- [ ] All file uploads validated for type (magic bytes, not just extension)
- [ ] File upload size limits enforced (application + Nginx level)
- [ ] SQL injection: all queries use parameterized statements (SQLAlchemy ORM)
- [ ] XSS: all user content sanitized before rendering (React escapes by default)
- [ ] Path traversal: file paths validated against allowed directories
- [ ] Command injection: no shell=True in subprocess calls
- [ ] SSRF prevention: URL inputs validated against allowlist of domains
- [ ] XML injection: XML parsing with defusedxml
- [ ] Zip bomb prevention: archive size limits on extraction

## Data Security

- [ ] Passwords hashed with bcrypt (cost factor ≥ 12)
- [ ] PII encrypted at rest (database-level or field-level encryption)
- [ ] Sensitive config in environment variables, not code
- [ ] `.env` file excluded from git (in .gitignore)
- [ ] Database backups encrypted (GPG or AES-256)
- [ ] MinIO server-side encryption enabled
- [ ] Qdrant data encryption at rest
- [ ] Audit logs tamper-protected (append-only)
- [ ] GDPR compliance: user data export/deletion endpoints implemented

## Infrastructure Security

- [ ] Non-root user in all Docker containers
- [ ] Docker images from official sources, pinned versions
- [ ] Regular image vulnerability scanning (Trivy, Grype)
- [ ] Kubernetes: Pod Security Standards (restricted profile)
- [ ] Kubernetes: Network policies restrict inter-pod communication
- [ ] Kubernetes: Secrets stored in external secret manager (Vault, AWS Secrets Manager)
- [ ] Kubernetes: RBAC roles follow least privilege
- [ ] Host OS hardened (disable unused services, automatic security updates)
- [ ] Firewall rules: only ports 80, 443, 22 (SSH) exposed
- [ ] SSH: key-based authentication only, root login disabled
- [ ] Fail2ban installed on SSH

## GPU Security

- [ ] NVIDIA driver regularly updated
- [ ] GPU process isolation (separate containers per tenant — future enhancement)
- [ ] Model files read-only mounted in containers
- [ ] CUDA out-of-memory handling prevents service crashes

## Monitoring & Incident Response

- [ ] Sentry error tracking configured with PII scrubbing
- [ ] Prometheus alerts configured for anomalies
- [ ] Security alerts: multiple failed logins, unusual API usage
- [ ] Audit logs include: user, action, IP, timestamp, resource
- [ ] Log aggregation (Loki/Elasticsearch) with 90-day retention
- [ ] Automated vulnerability scanning in CI/CD pipeline (Bandit, npm audit, Trivy)
- [ ] Incident response runbook documented
- [ ] On-call rotation established
- [ ] Data breach notification procedure established (GDPR: 72-hour notification)

## Supply Chain Security

- [ ] Dependencies pinned to exact versions in requirements.txt
- [ ] `pip audit` run in CI to detect vulnerable packages
- [ ] npm packages audited with `npm audit --audit-level=high`
- [ ] Docker base images regularly updated
- [ ] Internal package registry for air-gapped deployments
- [ ] Software Bill of Materials (SBOM) generated

## Business Continuity

- [ ] Daily automated backups with restore testing
- [ ] RTO (Recovery Time Objective) ≤ 4 hours
- [ ] RPO (Recovery Point Objective) ≤ 24 hours
- [ ] Disaster recovery runbook tested quarterly
- [ ] Multi-region backup storage
- [ ] Backup encryption keys stored separately from backups
- [ ] Monitoring alerts for backup failures

## Compliance

- [ ] GDPR data processing agreement with cloud providers
- [ ] Privacy policy published and accessible
- [ ] Terms of service published
- [ ] Data retention policies implemented (auto-delete after X days)
- [ ] User consent recorded for data processing
- [ ] Right to erasure (deletion) implemented
- [ ] Data portability (export) implemented
- [ ] Cookie consent (if applicable)

## Penetration Testing

- [ ] Annual penetration test by certified third party
- [ ] OWASP Top 10 addressed
- [ ] API security testing (OWASP API Security Top 10)
- [ ] Social engineering training for staff
- [ ] Bug bounty program (optional)

---

## Security Headers Checklist (HTTP Response)

Verify with: https://securityheaders.com

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-...'; ...
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Cache-Control: no-store (for authenticated API responses)
```

---

## Pre-Production Sign-Off

| Check | Owner | Date | Status |
|-------|-------|------|--------|
| Security headers verified | DevOps | - | - |
| SSL Labs A+ rating | DevOps | - | - |
| Dependency audit clean | Backend Lead | - | - |
| Pentest completed | Security Team | - | - |
| Backup restore tested | DevOps | - | - |
| Incident response reviewed | Engineering Lead | - | - |
| GDPR compliance verified | Legal | - | - |
| Admin MFA enabled | Admin | - | - |
