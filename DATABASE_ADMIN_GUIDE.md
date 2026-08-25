# Database Administration Guide

Operational procedures for maintaining the triage system database.

---

## Quick Reference

### Connect to Database

```bash
# Docker
docker exec -it triage_db psql -U triage_user -d triage_db

# Local
psql -U triage_user -d triage_db
```

### Common Tasks

```bash
# Backup
docker exec triage_db pg_dump -U triage_user triage_db > backup_$(date +%Y%m%d).sql

# Restore
docker exec -i triage_db psql -U triage_user -d triage_db < backup_20260822.sql

# View logs
docker logs triage_db

# Check size
docker exec triage_db du -sh /var/lib/postgresql/data
```

---

## Database Maintenance

### Regular Backups

**Daily backups (automated recommended):**

```bash
#!/bin/bash
# backup_daily.sh

BACKUP_DIR="/backups/triage"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="triage_db"
DB_USER="triage_user"

mkdir -p $BACKUP_DIR

docker exec triage_db pg_dump -U $DB_USER $DB_NAME | \
  gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: backup_$DATE.sql.gz"
```

**Run daily via cron:**
```bash
0 2 * * * /path/to/backup_daily.sh
```

### Restore from Backup

```bash
# Extract backup
gunzip backup_20260822_020000.sql.gz

# Restore to database
docker exec -i triage_db psql -U triage_user -d triage_db < backup_20260822_020000.sql

# Verify restoration
docker exec triage_db psql -U triage_user -d triage_db -c "SELECT COUNT(*) FROM patients;"
```

### Vacuum & Analyze

**Clean up and optimize database (monthly):**

```sql
-- Connect to database first
psql -U triage_user -d triage_db

-- Clean up deleted rows
VACUUM ANALYZE patients;
VACUUM ANALYZE vital_signs;
VACUUM ANALYZE triage_decisions;
VACUUM ANALYZE clinical_overrides;
VACUUM ANALYZE audit_logs;

-- Check table sizes
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Index Maintenance

**Check index usage (monthly):**

```sql
-- Find unused indexes
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;

-- Force index rebuild if needed
REINDEX INDEX index_name;
```

---

## Monitoring & Troubleshooting

### Check Database Health

```sql
-- Connection count
SELECT datname, count(*) as connections
FROM pg_stat_activity
GROUP BY datname;

-- Long-running queries
SELECT pid, usename, application_name, state, query_start,
       query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start ASC;

-- Cache hit ratio (should be >99%)
SELECT
  sum(heap_blks_read) as heap_read,
  sum(heap_blks_hit) as heap_hit,
  sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
FROM pg_statio_user_tables;

-- Table bloat
SELECT schemaname, tablename,
       round(100.0 * (CASE WHEN otta > 0 
       THEN sml.relpages - otta 
       ELSE 0 END) / sml.relpages, 2) AS table_waste_ratio
FROM pg_class sml
JOIN pg_namespace n ON (n.oid = sml.relnamespace)
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
  AND relpages > 1000
ORDER BY table_waste_ratio DESC;
```

### Monitor Slow Queries

Enable slow query logging:

```sql
-- Set in postgresql.conf or via command
ALTER SYSTEM SET log_min_duration_statement = 500;
SELECT pg_reload_conf();

-- View slow query log
docker exec triage_db tail -f /var/log/postgresql/postgresql.log | grep "duration:"
```

---

## Data Management

### Export Patient Data (for analysis)

```sql
-- Export all triage decisions
\copy (
  SELECT 
    p.patient_id,
    p.first_name,
    p.last_name,
    DATE_PART('year', AGE(p.date_of_birth)) as age,
    p.chief_complaint,
    vs.temperature_celsius,
    vs.heart_rate,
    vs.respiratory_rate,
    vs.oxygen_saturation,
    td.severity_score,
    td.confidence_score,
    td.triage_timestamp
  FROM triage_decisions td
  JOIN patients p ON p.patient_id = td.patient_id
  JOIN vital_signs vs ON vs.patient_id = p.patient_id
  WHERE td.triage_timestamp > NOW() - INTERVAL '30 days'
  ORDER BY td.triage_timestamp DESC
) TO '/tmp/triage_export.csv' WITH CSV HEADER;
```

### Archive Old Data (after 7+ years)

```sql
-- Export to archive before deletion
\copy (
  SELECT * FROM patients
  WHERE arrival_timestamp < NOW() - INTERVAL '7 years'
) TO '/archive/patients_pre_2019.csv' WITH CSV HEADER;

-- Delete from production
DELETE FROM patients
WHERE arrival_timestamp < NOW() - INTERVAL '7 years';

-- Vacuum to reclaim space
VACUUM FULL;
```

### Patient Audit Rights Query

```sql
-- Get complete audit trail for patient (for HIPAA audit right)
SELECT 
  l.log_id,
  l.event_type,
  l.event_description,
  l.event_timestamp,
  l.clinician_name,
  l.event_payload::jsonb
FROM audit_logs l
WHERE l.patient_id = 'PATIENT_ID_HERE'
ORDER BY l.event_timestamp ASC;
```

---

## Performance Tuning

### Connection Pool Configuration

Edit `docker-compose.yml` to adjust:

```yaml
environment:
  PGBOUNCER_POOL_MODE: transaction
  PGBOUNCER_MIN_POOL_SIZE: 10
  PGBOUNCER_DEFAULT_POOL_SIZE: 25
  PGBOUNCER_RESERVE_POOL_SIZE: 5
```

### Query Optimization

**Check execution plans:**

```sql
EXPLAIN ANALYZE
SELECT p.first_name, p.last_name, td.severity_score, td.triage_timestamp
FROM patients p
JOIN triage_decisions td ON p.patient_id = td.patient_id
WHERE td.triage_timestamp > NOW() - INTERVAL '1 hour'
ORDER BY td.triage_timestamp DESC;
```

**Add indexes for slow queries:**

```sql
-- If above query is slow, add:
CREATE INDEX idx_triage_timestamp ON triage_decisions(triage_timestamp DESC);
CREATE INDEX idx_patient_triage_time ON triage_decisions(patient_id, triage_timestamp DESC);
```

### Partition Large Tables (for 3+ years of data)

```sql
-- Partition audit_logs by year
CREATE TABLE audit_logs_2024 PARTITION OF audit_logs
  FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

CREATE TABLE audit_logs_2025 PARTITION OF audit_logs
  FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
```

---

## Compliance & Security

### Audit Log Integrity Verification

```sql
-- Verify no logs have been tampered with
SELECT log_id, event_type,
       checksum,
       encode(digest(event_payload, 'sha256'), 'hex') as calculated_checksum,
       CASE WHEN checksum = encode(digest(event_payload, 'sha256'), 'hex')
            THEN 'VALID'
            ELSE 'COMPROMISED'
       END as integrity_status
FROM audit_logs
ORDER BY event_timestamp DESC
LIMIT 100;
```

### Access Log (who accessed what)

```sql
-- Enable user login tracking
ALTER SYSTEM SET log_connections = on;
ALTER SYSTEM SET log_disconnections = on;
SELECT pg_reload_conf();

-- View access logs
docker exec triage_db grep "connection" /var/log/postgresql/postgresql.log | tail -100
```

### Encryption at Rest (PostgreSQL)

```bash
# Create encrypted backup
gpg --symmetric backup_20260822.sql

# Restore encrypted backup
gpg --decrypt backup_20260822.sql.gpg | \
  docker exec -i triage_db psql -U triage_user -d triage_db
```

---

## Disaster Recovery

### Full System Backup & Restore

**Backup entire container state:**

```bash
# Stop services
docker-compose down

# Backup PostgreSQL volume
docker run --rm -v triage_db:/data -v $(pwd):/backup \
  ubuntu tar czf /backup/triage_db_full_$(date +%Y%m%d).tar.gz /data

# Start services
docker-compose up -d
```

**Restore from full backup:**

```bash
# Stop services
docker-compose down

# Remove old volume
docker volume rm triage_db

# Create new volume and restore
docker volume create triage_db

docker run --rm -v triage_db:/data -v $(pwd):/backup \
  ubuntu tar xzf /backup/triage_db_full_20260822.tar.gz -C /

# Start services
docker-compose up -d
```

### Test Restoration Procedure (monthly)

```bash
# 1. Create test environment
docker-compose -f docker-compose.test.yml up -d

# 2. Restore backup to test
docker exec -i triage_db_test psql -U triage_user -d triage_db < backup.sql

# 3. Run queries to verify
docker exec triage_db_test psql -U triage_user -d triage_db << EOF
  SELECT COUNT(*) FROM patients;
  SELECT COUNT(*) FROM audit_logs;
  SELECT MAX(event_timestamp) FROM audit_logs;
EOF

# 4. Test API connectivity
curl http://localhost:8001/health

# 5. Clean up
docker-compose -f docker-compose.test.yml down -v
```

---

## User & Permission Management

### Create Read-Only User (for reporting)

```sql
-- Create reporting user
CREATE USER triage_reporter WITH PASSWORD 'secure_password';

-- Grant read-only access
GRANT CONNECT ON DATABASE triage_db TO triage_reporter;
GRANT USAGE ON SCHEMA public TO triage_reporter;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO triage_reporter;

-- Set defaults for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO triage_reporter;
```

### Create Admin User

```sql
CREATE USER triage_admin WITH PASSWORD 'admin_password';
ALTER USER triage_admin WITH SUPERUSER;
```

### Revoke Permissions

```sql
-- Disable user without deleting
ALTER USER triage_user WITH NOLOGIN;

-- Re-enable
ALTER USER triage_user WITH LOGIN;

-- Delete user
DROP USER triage_admin;
```

---

## Monitoring Alerts (Example)

### Prometheus Metrics

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']  # postgres_exporter
    
  - job_name: 'api'
    static_configs:
      - targets: ['localhost:8000']
```

### Sample Alerts

```yaml
# rules.yml
groups:
  - name: triage_alerts
    rules:
      - alert: HighDiskUsage
        expr: node_filesystem_avail_bytes{mountpoint="/var/lib/postgresql"} < 1e9
        for: 5m
        annotations:
          summary: "PostgreSQL disk usage high"
      
      - alert: ConnectionPoolExhausted
        expr: pg_stat_activity_count > 25
        for: 5m
        annotations:
          summary: "Database connection pool at limit"
      
      - alert: SlowQueries
        expr: pg_stat_statements_mean_exec_time > 1000
        for: 5m
        annotations:
          summary: "Slow queries detected"
```

---

## Checklist

### Daily
- [ ] Check API health: `curl http://localhost:8000/health`
- [ ] Monitor queue depth: `SELECT COUNT(*) FROM patients WHERE arrival_timestamp > NOW() - INTERVAL '8 hours';`
- [ ] Check for errors: `docker logs triage_api | grep ERROR`

### Weekly
- [ ] Review audit logs: `SELECT COUNT(*) FROM audit_logs WHERE event_timestamp > NOW() - INTERVAL '7 days';`
- [ ] Check database size: `SELECT pg_size_pretty(pg_database_size('triage_db'));`
- [ ] Verify backup completion

### Monthly
- [ ] Run VACUUM ANALYZE on all tables
- [ ] Review index usage
- [ ] Test backup restoration
- [ ] Check slow query log
- [ ] Verify integrity checksums

### Quarterly
- [ ] Review and archive old data
- [ ] Update statistics
- [ ] Performance tuning review
- [ ] Security audit

---

## Emergency Procedures

### Database Won't Start

```bash
# Check logs
docker logs triage_db

# Restart container
docker-compose restart postgres

# If still failing, check disk space
docker exec triage_db df -h

# Check PostgreSQL data integrity
docker exec triage_db pg_basebackup -v
```

### Corrupted Data

```sql
-- Check table integrity
REINDEX TABLE patients;
REINDEX TABLE vital_signs;
REINDEX TABLE triage_decisions;
REINDEX TABLE audit_logs;

-- Repair if needed
VACUUM FULL ANALYZE;
```

### Performance Degradation

```bash
# Kill long-running queries
docker exec triage_db psql -U triage_user -d triage_db -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
   WHERE state = 'active' AND query_start < NOW() - INTERVAL '10 minutes';"

# Restart if needed
docker-compose restart postgres
```

---

## References

- PostgreSQL Documentation: https://www.postgresql.org/docs/
- pg_stat_statements: https://www.postgresql.org/docs/current/pgstatstatements.html
- HIPAA Database Audit: https://www.hipaajournal.com/database-auditing/

---

**Database Admin Team** - Keep this guide on hand!
