# Runbook: Flag Leakage
## Severity: HIGH | RTO: 15 minutes | RPO: N/A

### Symptoms
- Team reporting duplicate flags
- Unusual solve patterns detected
- Flag appears in public channels/forums
- Sudden score changes indicating exploitation

### Immediate Actions

#### 1. Verify the Leak
```bash
# Check for flag usage anomalies
kubectl exec -n cerberus deploy/backend -- python -c "
from app.core.database import SessionLocal
from app.domain.challenges.entities import Submission

db = SessionLocal()
# Look for submissions with unusual timing patterns
suspicious = db.query(Submission).filter(
    Submission.created_at > NOW() - INTERVAL '1 hour'
).group_by(Submission.team_id, Submission.challenge_id).having(
    Submission.count > 10
).all()
print(f'Found {len(suspicious)} suspicious patterns')
"

# Check flag validity
kubectl exec -n cerberus deploy/backend -- python -c "
from app.domain.challenges.services import FlagValidator
validator = FlagValidator()
flags = validator.get_active_flags()
print(f'Active flags: {len(flags)}')
"
```

#### 2. Rotate Compromised Flags
```bash
# Get compromised challenge
CHALLENGE_ID="<CHALLENGE_ID>"

# Generate new flag
NEW_FLAG=$(python3 -c "import secrets; print('CTF{' + secrets.token_hex(16) + '}')")
echo "New flag: $NEW_FLAG"

# Update challenge
kubectl exec -n cerberus deploy/backend -- python -c "
from app.core.database import SessionLocal
from app.domain.challenges.entities import Challenge

db = SessionLocal()
challenge = db.query(Challenge).filter_by(id='$CHALLENGE_ID').first()
challenge.flag = '$NEW_FLAG'
db.commit()
print('Flag rotated')
"

# Invalidate old flags
kubectl exec -n cerberus deploy/backend -- python -c "
from app.core.database import SessionLocal
from app.domain.challenges.entities import Submission

db = SessionLocal()
# Invalidate submissions with old flag
submissions = db.query(Submission).filter(
    Submission.challenge_id == '$CHALLENGE_ID',
    Submission.created_at > NOW() - INTERVAL '2 hours'
).all()

for s in submissions:
    s.is_valid = False
    s.points = 0
db.commit()
print(f'Invalidated {len(submissions)} submissions')
"
```

#### 3. Notify Affected Teams
```bash
# Send notification to teams
kubectl exec -n cerberus deploy/backend -- python -c "
from app.core.database import SessionLocal
from app.domain.teams.entities import Team
from app.application.notification.service import NotificationService

db = SessionLocal()
notification = NotificationService()

teams = db.query(Team).filter(Team.is_active == True).all()
for team in teams:
    notification.send(
        team.id,
        'flag_compromise',
        {
            'title': 'Flag Compromise Detected',
            'message': 'A security incident has been detected involving one or more challenges. Points may be adjusted.',
        }
    )
print(f'Notified {len(teams)} teams')
"
```

### Investigation

#### 1. Identify the Leak Source
```bash
# Check for unauthorized access patterns
kubectl logs -n cerberus deploy/backend --since=2h | grep -i "flag" | grep -v "submit"

# Review WebSocket connections
kubectl logs -n cerberus deploy/realtime --since=2h | grep -i "flag"

# Check for external communications
kubectl logs -n cerberus deploy/backend --since=2h | grep -E "http://|https://" | grep -v api
```

#### 2. Check for Exploit Code
```bash
# Look for automated submission patterns
kubectl exec -n cerberus deploy/backend -- python -c "
from app.core.database import SessionLocal
from app.domain.challenges.entities import Submission

db = SessionLocal()
# Check for rapid submissions (< 1 second between)
rapid = db.execute('''
    SELECT user_id, COUNT(*) as cnt
    FROM submissions
    WHERE created_at > NOW() - INTERVAL '2 hours'
    GROUP BY user_id
    HAVING MIN(created_at - LAG(created_at) OVER (ORDER BY created_at)) < INTERVAL '1 second'
''').fetchall()
print(f'Found {len(rapid)} rapid submission patterns')
"
```

### Containment

#### 1. Disable Challenge Temporarily
```bash
# Disable the challenge
kubectl exec -n cerberus deploy/backend -- python -c "
from app.core.database import SessionLocal
from app.domain.challenges.entities import Challenge

db = SessionLocal()
challenge = db.query(Challenge).filter_by(id='$CHALLENGE_ID').first()
challenge.is_active = False
db.commit()
print('Challenge disabled')
"
```

#### 2. Enable Enhanced Monitoring
```bash
# Increase logging verbosity
kubectl set env deployment/backend LOG_LEVEL=debug -n cerberus

# Enable flag submission validation
kubectl set env deployment/backend FLAG_VALIDATION_STRICT=true -n cerberus
```

### Recovery

#### 1. Restore Fair Competition
```bash
# Reset scores for compromised challenge
kubectl exec -n cerberus deploy/backend -- python -c "
from app.core.database import SessionLocal
from app.domain.challenges.entities import Submission
from app.domain.teams.entities import TeamScore

db = SessionLocal()
# Recalculate scores excluding compromised submissions
db.execute('DELETE FROM team_scores WHERE challenge_id = :cid', {'cid': '$CHALLENGE_ID'})
db.commit()
print('Scores reset')
"

# Notify teams of score adjustments
kubectl exec -n cerberus deploy/backend -- python -c "
from app.application.notification.service import NotificationService
notification = NotificationService()
notification.broadcast(
    'score_adjustment',
    {
        'message': 'Scores for challenge <CHALLENGE_NAME> have been adjusted due to a security incident.',
    }
)
"
```

#### 2. Re-enable Challenge
```bash
# After investigation and flag rotation
kubectl exec -n cerberus deploy/backend -- python -c "
from app.core.database import SessionLocal
from app.domain.challenges.entities import Challenge

db = SessionLocal()
challenge = db.query(Challenge).filter_by(id='$CHALLENGE_ID').first()
challenge.is_active = True
db.commit()
print('Challenge re-enabled')
"
```

### Post-Incident Actions

1. **Review challenge security:**
   - Check for unintended flag exposure
   - Review challenge writeup for leaks
   - Verify sandbox isolation

2. **Update anti-cheat measures:**
   ```python
   # Enhanced flag validation
   class EnhancedFlagValidator:
       def validate(self, flag: str, team_id: str, challenge_id: str) -> bool:
           # Check for rapid submissions
           if self.is_rapid_submission(team_id, challenge_id):
               return False
           # Check for multiple IPs
           if self.is_multi_ip_submission(team_id, challenge_id):
               return False
           # Check for automation
           if self.detects_automation(team_id):
               return False
           return True
   ```

3. **Document findings:**
   - How flag was leaked
   - Teams affected
   - Corrective actions
   - Preventive measures

### Preventive Measures

1. Implement flag submission rate limiting
2. Add flag submission IP validation
3. Enable behavioral analysis for submissions
4. Regular challenge security reviews
5. Player education on responsible disclosure

### Contact
- Admin Team: admin@cerberus.example.com
- Security: security@cerberus.example.com
