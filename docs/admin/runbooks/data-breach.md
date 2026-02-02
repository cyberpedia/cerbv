# Runbook: Data Breach (GDPR Incident)
## Severity: CRITICAL | RTO: 1 hour | RPO: N/A

### Symptoms
- Unauthorized access detected to user data
- PII exposure in logs
- Suspicious database queries
- User reports unauthorized account access

### Immediate Actions (GDPR Article 33 - 72 hours to notify)

#### 1. Contain the Breach
```bash
# Block suspicious IPs
iptables -A INPUT -s <SUSPICIOUS_IP> -j DROP

# Rotate all secrets
kubectl get secrets -n cerberus -o yaml > /tmp/secrets_backup_$(date +%Y%m%d).yaml
kubectl apply -f /opt/cerberus/k8s/base/secret.yaml

# Invalidate all active sessions
kubectl exec -n cerberus deploy/redis -- redis-cli FLUSHALL

# Disable compromised accounts
kubectl exec -n cerberus deploy/backend -- python -c "
from app.core.database import SessionLocal
from app.domain.users.entities import User
db = SessionLocal()
users = db.query(User).filter(User.id.in_(['<USER_IDS>'])).all()
for u in users:
    u.is_active = False
db.commit()
"
```

#### 2. Preserve Evidence
```bash
# Capture database state
pg_dump -h postgres-primary -U postgres cerberus > /tmp/db_dump_breach_$(date +%Y%m%d_%H%M%S).sql

# Save audit logs
kubectl logs -n cerberus deploy/backend --since=24h > /tmp/backend_logs_breach_$(date +%Y%m%d_%H%M%S).log

# Capture network logs
kubectl logs -n monitoring -l app=traefik --since=24h > /tmp/traefik_logs_breach_$(date +%Y%m%d_%H%M%S).log
```

### Assessment

#### 1. Determine Scope
```bash
# Check accessed tables
psql -h postgres-primary -U postgres cerberus -c "
SELECT * FROM audit.logs 
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
"

# Identify affected users
psql -h postgres-primary -U postgres cerberus -c "
SELECT DISTINCT user_id, COUNT(*) as access_count
FROM audit.logs 
WHERE created_at > NOW() - INTERVAL '24 hours'
  AND action LIKE '%SELECT%'
  AND user_id IS NOT NULL
GROUP BY user_id
ORDER BY access_count DESC;
"
```

#### 2. Document Data Types Exposed
| Data Type | Users Affected | Risk Level |
|-----------|---------------|------------|
| Email addresses | TBD | Medium |
| Password hashes | TBD | High |
| IP addresses | TBD | Low |
| Solve history | TBD | Low |

### GDPR Notification Requirements

#### 1. Document the Breach
- Date and time of discovery
- Nature of the breach
- Categories of data subjects
- Approximate number of data subjects
- Categories of personal data
- Likely consequences
- Measures taken

#### 2. Notify Supervisory Authority (within 72 hours)
```markdown
To: [Supervisory Authority Email]
Subject: GDPR Article 33 - Personal Data Breach Notification

Dear Data Protection Officer,

In accordance with Article 33 of the General Data Protection Regulation (GDPR),
we are notifying you of a personal data breach affecting the Cerberus CTF Platform.

1. Date of breach discovery: [DATE]
2. Nature of the breach: [DESCRIPTION]
3. Categories of data affected: [EMAIL, PASSWORD HASHES, ETC.]
4. Approximate number of data subjects: [NUMBER]
5. Likely consequences: [DESCRIPTION]
6. Measures taken: [CONTAINMENT, REMEDIATION]

We will provide updates as our investigation continues.

Sincerely,
[Data Protection Officer Name]
[Organization]
```

#### 3. Notify Affected Users (without undue delay)
```bash
# Generate user notification emails
kubectl exec -n cerberus deploy/backend -- python -c "
from app.core.database import SessionLocal
from app.domain.users.entities import User
from app.application.notification.service import EmailService

db = SessionLocal()
email_service = EmailService()

users = db.query(User).filter(User.is_active == True).all()
for user in users:
    email_service.send_template(
        user.email,
        'data_breach_notification',
        {
            'user_name': user.username,
            'breach_date': '2024-01-01',
            'affected_data': ['email address'],
            'actions_taken': ['Session invalidation', 'Secret rotation'],
            'recommendations': ['Change password', 'Enable 2FA'],
        }
    )
"
```

### Recovery Steps

1. **Rotate all credentials:**
   ```bash
   # Database passwords
   kubectl apply -f /opt/cerberus/k8s/base/secret.yaml
   
   # API keys
   # JWT secrets
   # Encryption keys
   ```

2. **Enable enhanced logging:**
   ```python
   # In backend config
   LOG_LEVEL: "debug"
   AUDIT_LOGGING: true
   SENSITIVE_DATA_MASKING: true
   ```

3. **Review and update access controls:**
   ```bash
   # Check current permissions
   kubectl auth can-i --list --namespace=cerberus
   
   # Review RBAC
   kubectl get rolebindings -n cerberus -o yaml > /tmp/rbac_review_$(date +%Y%m%d).yaml
   ```

### Post-Incident Documentation

1. **Complete incident report:**
   - Timeline of events
   - Root cause analysis
   - Impact assessment
   - Response effectiveness
   - Lessons learned

2. **Update security policies:**
   - Access control review
   - Encryption at rest/flight
   - Monitoring and alerting
   - Incident response procedures

3. **GDPR compliance updates:**
   - Update privacy policy
   - Review consent mechanisms
   - Update data processing agreements

### Contact
- DPO: dpo@cerberus.example.com
- Legal: legal@cerberus.example.com
- Supervisory Authority: [Local Authority]
