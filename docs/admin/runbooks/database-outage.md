# Runbook: Database Outage
## Severity: CRITICAL | RTO: 4 hours | RPO: 15 minutes

### Symptoms
- API returns 500 errors
- `pg_isready` fails
- Database connection pool exhausted
- Leaderboard not updating

### Immediate Actions

#### 1. Assess the Situation
```bash
# Check PostgreSQL status
kubectl logs -n cerberus deploy/postgres-primary --tail=100

# Check for connection issues
kubectl exec -n cerberus deploy/postgres-primary -- psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Check disk space
kubectl exec -n cerberus deploy/postgres-primary -- df -h /var/lib/postgresql
```

#### 2. Check Patroni Status
```bash
# Check Patroni leader
kubectl exec -n cerberus deploy/postgres-primary -- patronictl list

# Verify replication lag
kubectl exec -n cerberus deploy/postgres-primary -- psql -U postgres -c "SELECT client_addr, state, sync_state, sent_lsn, replay_lag FROM pg_stat_replication;"
```

#### 3. Attempt Automatic Failover (if needed)
```bash
# If primary is down, trigger failover
kubectl exec -n cerberus deploy/postgres-primary -- patronictl failover --cluster cerberus-cluster --candidate postgres-replica
```

### Recovery Steps

#### If Primary is Unresponsive
```bash
# 1. Scale down application
kubectl scale deployment/cerberus-backend --replicas=0 -n cerberus

# 2. Verify replica is promoted
kubectl exec -n cerberus deploy/postgres-replica -- patronictl list

# 3. Update connection strings if needed
# (Patroni should handle this automatically)

# 4. Scale up application
kubectl scale deployment/cerberus-backend --replicas=3 -n cerberus

# 5. Verify health
curl http://localhost:8000/health
```

#### If Disk is Full
```bash
# 1. Identify largest tables
kubectl exec -n cerberus deploy/postgres-primary -- psql -U postgres -d cerberus -c "
SELECT schemaname, tablename, pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables ORDER BY pg_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;
"

# 2. Clean up old data (audit logs, sessions)
kubectl exec -n cerberus deploy/postgres-primary -- psql -U postgres -d cerberus -c "
DELETE FROM audit.logs WHERE created_at < NOW() - INTERVAL '90 days';
VACUUM FULL audit.logs;
"

# 3. Clean up WAL archives
kubectl exec -n cerberus deploy/postgres-primary -- pg_archivecleanup /var/lib/postgresql/pg_wal $(ls -t /var/lib/postgresql/pg_wal/*.backup | tail -1)
```

### Post-Incident Actions

1. **Verify data integrity:**
   ```bash
   kubectl exec -n cerberus deploy/postgres-primary -- psql -U postgres -d cerberus -c "
   SELECT schemaname, tablename, n_live_tup, n_dead_tup, last_vacuum 
   FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 10;
   "
   ```

2. **Review logs for root cause:**
   ```bash
   kubectl logs -n cerberus deploy/postgres-primary --since=24h | grep -i error
   ```

3. **Document incident:**
   - Time of detection
   - Root cause
   - Actions taken
   - Data loss (if any)
   - Preventive measures

### Preventive Measures

1. Enable automated vacuum
2. Set up WAL archiving to S3
3. Monitor disk usage with alerts
4.定期进行备份恢复测试

### Contact
- Primary: DBA Team (dba-team@example.com)
- Escalation: Platform Engineering (platform@example.com)
