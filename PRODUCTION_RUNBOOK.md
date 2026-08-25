# Production Deployment Runbook

**Complete checklist for going live with the triage system.**

---

## Phase 1: Pre-Deployment (Weeks 1-2)

### Security & Compliance

- [ ] **Change all default passwords**
  ```bash
  # In docker-compose.yml and k8s/secret.yaml
  POSTGRES_PASSWORD: $(openssl rand -base64 32)
  SECRET_KEY: $(openssl rand -base64 32)
  ```

- [ ] **Enable SSL/TLS**
  - [ ] Request SSL certificate (Let's Encrypt or CA)
  - [ ] Configure Nginx reverse proxy
  - [ ] Set HTTPS only, redirect HTTP → HTTPS
  - [ ] Test certificate: `openssl s_client -connect yourhospital.com:443`

- [ ] **Add authentication**
  - [ ] Implement OAuth2 or API key authentication
  - [ ] Create user roles (Admin, Clinician, Reporter)
  - [ ] Set up MFA for admin accounts

- [ ] **Data protection**
  - [ ] Enable encryption at rest (PGCrypto in PostgreSQL)
  - [ ] Enable encryption in transit (TLS)
  - [ ] Implement PII masking for backups

- [ ] **Audit logging**
  - [ ] Verify audit_logs table implementation
  - [ ] Test checksum verification
  - [ ] Configure log retention (7 years for HIPAA)
  - [ ] Set up centralized logging (ELK, Splunk, etc.)

- [ ] **HIPAA compliance**
  - [ ] Have legal/compliance team review
  - [ ] Document data handling procedures
  - [ ] Create Business Associate Agreement (BAA)
  - [ ] Set up incident response plan

### Infrastructure Setup

- [ ] **Production database**
  - [ ] Provision PostgreSQL 15+ with replication
  - [ ] Configure automated backups (daily)
  - [ ] Test backup restoration
  - [ ] Set up monitoring & alerting
  - [ ] Plan disaster recovery (RTO/RPO)

- [ ] **Application server**
  - [ ] Provision production VM/cloud instance
  - [ ] Install dependencies (Python 3.11+, etc.)
  - [ ] Configure load balancer
  - [ ] Set up auto-scaling rules

- [ ] **Networking**
  - [ ] Configure VPN/firewall rules
  - [ ] Whitelist hospital networks only
  - [ ] Set up WAF (Web Application Firewall)
  - [ ] Test DDoS mitigation

- [ ] **Monitoring & Alerting**
  - [ ] Set up Prometheus + Grafana
  - [ ] Create dashboards (queue depth, latency, errors)
  - [ ] Configure Slack/PagerDuty alerts
  - [ ] Set alert thresholds

### Documentation & Training

- [ ] **Create runbooks**
  - [ ] Setup guide
  - [ ] Deployment procedures
  - [ ] Troubleshooting guide
  - [ ] Emergency procedures

- [ ] **Staff training**
  - [ ] ED nurses: How to use system
  - [ ] Physicians: Override procedures
  - [ ] IT team: Monitoring & maintenance
  - [ ] Compliance: Audit log review

- [ ] **Create operational procedures**
  - [ ] Daily checks
  - [ ] Weekly maintenance
  - [ ] Monthly backups
  - [ ] Quarterly audits

---

## Phase 2: Staging Deployment (Week 2-3)

### Staging Environment Setup

- [ ] **Mirror production**
  - [ ] Use same OS, database version
  - [ ] Same hardware specs (or close)
  - [ ] Same network configuration
  - [ ] Copy production-like data (anonymized)

- [ ] **Deploy system**
  ```bash
  # Docker
  docker-compose -f docker-compose.prod.yml up -d
  
  # OR Kubernetes
  kubectl apply -f k8s/ -n staging
  ```

- [ ] **Run full test suite**
  ```bash
  python test_workflow.py
  python performance_test.py
  ```

- [ ] **Load test (3x volume)**
  ```bash
  # Generate surge patients
  python -c "
    from simulated_data import SimulatedPatientGenerator
    surge = SimulatedPatientGenerator.generate_surge_scenario(
      base_arrival_rate=10,
      surge_multiplier=3,
      duration_minutes=60
    )
    # Simulate intake
  "
  ```

- [ ] **Integration testing**
  - [ ] Test with EHR system (if applicable)
  - [ ] Verify audit logging
  - [ ] Test backup/restore
  - [ ] Verify monitoring alerts

### Clinician Acceptance Testing

- [ ] **Pilot with 5-10 nurses**
  - [ ] Have them score 50+ patients
  - [ ] Gather feedback on UI/UX
  - [ ] Test override workflow
  - [ ] Measure adoption rate

- [ ] **Physician review**
  - [ ] Score agreement with 10 physicians
  - [ ] Test override reasons
  - [ ] Check confidence scores
  - [ ] Review red flag accuracy

### Performance Validation

- [ ] **Latency**
  ```
  ✓ Intake + Triage: <500ms
  ✓ Queue query: <100ms
  ✓ Audit query: <200ms
  ```

- [ ] **Throughput**
  ```
  ✓ 20+ patients/sec (intake)
  ✓ 5+ patients/sec (triage)
  ✓ 3x surge handling
  ```

- [ ] **Reliability**
  ```
  ✓ 99.9% uptime
  ✓ Zero data loss
  ✓ Audit trail complete
  ```

---

## Phase 3: Production Deployment (Week 3-4)

### Pre-Go-Live Checks

- [ ] **Database**
  - [ ] Backup in place
  - [ ] Replication verified
  - [ ] Monitoring active
  - [ ] Passwords changed

- [ ] **Application**
  - [ ] All dependencies installed
  - [ ] Health check passing
  - [ ] Logs flowing to central system
  - [ ] Metrics being collected

- [ ] **Security**
  - [ ] SSL/TLS working
  - [ ] Authentication enabled
  - [ ] Authorization rules in place
  - [ ] Firewall rules active

- [ ] **Monitoring**
  - [ ] Dashboards displaying data
  - [ ] Alerts configured
  - [ ] On-call schedule set
  - [ ] Escalation contacts defined

- [ ] **Documentation**
  - [ ] All runbooks ready
  - [ ] Emergency contacts posted
  - [ ] Backup procedures verified
  - [ ] Recovery time confirmed

### Go-Live Plan

**Step 1: Enable System (Morning Shift)**
```bash
# Start application
docker-compose -f docker-compose.prod.yml up -d
# OR
kubectl apply -f k8s/ -n production

# Verify health
curl https://yourhospital.com/health
```

**Step 2: Load Sample Data (Training)**
```bash
# Optional: load test data for training
curl -X POST "https://yourhospital.com/demo/load-sample-patients?num_patients=20"
```

**Step 3: Soft Launch (Nurses Only)**
- 2-4 hours
- Limited to 1-2 nurses
- Monitor closely
- Gather real feedback

**Step 4: Expand (Morning Shift Only)**
- 4-8 hours
- Expand to 5-10 nurses
- One ED physician monitoring
- Capture override reasons

**Step 5: Full Deployment**
- If no critical issues, expand to full ED
- All shifts active
- 24/7 support on standby
- Daily review meetings

### Day-1 Monitoring (Live)

Every 30 minutes:
```bash
# Check system health
curl https://yourhospital.com/health

# Check queue depth
curl https://yourhospital.com/metrics/surge

# Review error logs
docker logs triage_api | grep ERROR

# Monitor database
docker exec triage_db psql -U triage_user -c "SELECT COUNT(*) FROM patients;"
```

Every 2 hours:
```bash
# Review override report
curl https://yourhospital.com/audit/overrides?hours=2

# Check wait times
curl https://yourhospital.com/queue

# Verify backups
ls -lh /backups/triage/backup_*.sql.gz | tail -5
```

---

## Phase 4: Post-Deployment (Ongoing)

### First Week

**Daily:**
- [ ] Review override report (catch concerning patterns)
- [ ] Check system health dashboard
- [ ] Review error logs
- [ ] Monitor queue metrics
- [ ] Verify backup completion

**Clinician Feedback:**
- [ ] Collect feedback from nurses
- [ ] Collect feedback from physicians
- [ ] Log issues in tracking system
- [ ] Prioritize fixes

**Adjustments:**
- [ ] Fine-tune thresholds if needed
- [ ] Adjust chief complaint keywords
- [ ] Improve documentation
- [ ] Update training materials

### First Month

**Weekly:**
- [ ] Review all override patterns
- [ ] Analyze triage accuracy
- [ ] Check performance metrics
- [ ] Review security logs
- [ ] Team meeting with ED leadership

**Monthly:**
- [ ] Full system audit
- [ ] Performance review
- [ ] Compliance audit
- [ ] Update runbooks
- [ ] Plan improvements

### Ongoing

**Monthly Checks:**
- [ ] Database maintenance (VACUUM, ANALYZE)
- [ ] Backup testing (restore to staging)
- [ ] Security update review
- [ ] Performance tuning
- [ ] Compliance verification

**Quarterly:**
- [ ] Full compliance audit
- [ ] HIPAA audit trail review
- [ ] Disaster recovery drill
- [ ] Performance benchmarking
- [ ] Staff training refresh

---

## Emergency Procedures

### System Down

1. **Detect** (monitoring alerts)
2. **Notify** (page on-call engineer)
3. **Diagnose**
   ```bash
   curl https://yourhospital.com/health  # Check API
   docker logs triage_api | tail -50     # Check logs
   docker ps                               # Check containers
   ```
4. **Mitigation**
   - Restart API: `docker-compose restart triage_api`
   - Restart DB: `docker-compose restart postgres`
   - Fall back to paper forms
5. **Restore** (restore from backup if data corruption)
6. **Post-mortem** (within 24 hours)

### Data Corruption

1. **Stop the system** (prevent further damage)
2. **Restore from backup**
   ```bash
   docker exec -i triage_db psql -U triage_user -d triage_db < backup_last_good.sql
   ```
3. **Verify data integrity**
   ```bash
   docker exec triage_db psql -U triage_user -c "SELECT COUNT(*) FROM patients;"
   ```
4. **Restart system**
   ```bash
   docker-compose up -d
   ```
5. **Notify affected clinicians** (which patients affected?)
6. **Audit review** (what went wrong?)

### Security Breach

1. **Isolate** (take system offline if necessary)
2. **Assess** (what data accessed?)
3. **Notify** (hospital security, legal, patients if required)
4. **Review logs** (who, what, when)
   ```bash
   docker exec triage_db psql -U triage_user -c \
     "SELECT * FROM audit_logs WHERE event_timestamp > NOW() - INTERVAL '1 hour';"
   ```
5. **Patch** (fix vulnerability)
6. **Restore** (if backups compromised)
7. **Follow up** (incident report, improvement plan)

---

## Troubleshooting Quick Reference

### API Not Responding

```bash
# 1. Check if running
docker ps | grep triage_api

# 2. Check logs
docker logs triage_api

# 3. Restart
docker-compose restart triage_api

# 4. Check database connection
docker logs triage_api | grep "DATABASE_URL"
```

### Database Connection Error

```bash
# 1. Check if database is running
docker ps | grep postgres

# 2. Check database logs
docker logs triage_db

# 3. Check connection string
echo $DATABASE_URL

# 4. Verify credentials
docker exec triage_db psql -U triage_user -c "SELECT 1;"
```

### Slow Queries

```bash
# 1. Check current connections
docker exec triage_db psql -U triage_user -c \
  "SELECT pid, usename, state FROM pg_stat_activity;"

# 2. Kill long-running queries
docker exec triage_db psql -U triage_user -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
   WHERE state = 'active' AND query_start < NOW() - INTERVAL '10 minutes';"

# 3. Check slow query log
docker exec triage_db grep "duration:" /var/log/postgresql/postgresql.log | sort -rn | head -20
```

### High Disk Usage

```bash
# 1. Check disk space
docker exec triage_db df -h /var/lib/postgresql/data

# 2. Find large tables
docker exec triage_db psql -U triage_user -c \
  "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
   FROM pg_tables ORDER BY pg_total_relation_size DESC;"

# 3. Archive old data
docker exec triage_db psql -U triage_user -c \
  "DELETE FROM patients WHERE arrival_timestamp < NOW() - INTERVAL '7 years';"

# 4. Vacuum
docker exec triage_db psql -U triage_user -c "VACUUM FULL ANALYZE;"
```

---

## Success Metrics

**After 1 Month:**
- [ ] 99.9% system uptime
- [ ] 95%+ clinician acceptance rate
- [ ] <500ms triage latency (p95)
- [ ] Zero data loss incidents
- [ ] Complete audit trail (no missing logs)
- [ ] <5% override rate (clinician agreement with system)

**After 3 Months:**
- [ ] 99.95% uptime
- [ ] Triage accuracy measured against physician reference standard
- [ ] Mean wait time reduced by 10-15%
- [ ] Override reasons catalogued and analyzed
- [ ] System calibrated for local patient population

---

## Escalation Contacts

```
Tier 1 (Application Support)
  Name: ________________
  Phone: _______________
  Email: ________________
  Hours: 7am - 7pm weekdays

Tier 2 (Database/Infrastructure)
  Name: ________________
  Phone: _______________
  Email: ________________
  Hours: 24/7

Tier 3 (Management On-Call)
  Name: ________________
  Phone: _______________
  Email: ________________
  Hours: Escalation only

Hospital IT Department
  Phone: _______________
  Email: ________________

Compliance Officer
  Name: ________________
  Phone: _______________
  Email: ________________
```

---

## Sign-Off

- [ ] **Project Lead**: ________________ Date: ______
- [ ] **IT Director**: ________________ Date: ______
- [ ] **ED Medical Director**: ________________ Date: ______
- [ ] **Compliance Officer**: ________________ Date: ______
- [ ] **Hospital Administrator**: ________________ Date: ______

---

**Ready for production!** 🚀
