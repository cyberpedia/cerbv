# Runbook: Challenge Sandbox Escape
## Severity: CRITICAL | RTO: 5 minutes | RPO: N/A

### Symptoms
- Unexpected network connections from challenge container
- Access to host resources from challenge
- Escape to host namespace
- Unauthorized access to cluster resources

### Immediate Actions

#### 1. Isolate the Challenge
```bash
# Get the challenge instance
INSTANCE_ID=$(kubectl get instances -n challenge-namespace -l "challenge-id=<CHALLENGE_ID>" -o jsonpath='{.items[0].metadata.name}')

# Delete the instance immediately
kubectl delete instance "$INSTANCE_ID" -n challenge-namespace --force --grace-period=0

# Scale down orchestrator to prevent new spawns
kubectl scale deployment/cerberus-orchestrator --replicas=0 -n cerberus
```

#### 2. Block Network Egress
```bash
# Apply emergency network policy to block all egress
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: emergency-deny-all
  namespace: challenge-namespace
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress: []
EOF
```

#### 3. Preserve Evidence
```bash
# Capture container forensics
kubectl debug -n challenge-namespace instance/<INSTANCE_ID> --image=busybox -- /bin/sh

# Save network logs
kubectl logs -n challenge-namespace instance/<INSTANCE_ID> > /tmp/challenge_logs_$(date +%Y%m%d_%H%M%S).log

# Capture network connections
kubectl exec -n challenge-namespace instance/<INSTANCE_ID> -- netstat -anp 2>/dev/null || true
```

### Investigation Steps

#### 1. Review Audit Logs
```bash
# Check challenge spawn logs
kubectl logs -n cerberus deployment/cerberus-orchestrator --since=1h | grep "<CHALLENGE_ID>"

# Check for network policy violations
kubectl get networkpolicies -n challenge-namespace -o yaml

# Review Falco alerts
kubectl logs -n monitoring -l app=falco --since=1h | grep "<INSTANCE_ID>"
```

#### 2. Analyze the Escape Vector
```bash
# Check container security context
kubectl get instance <INSTANCE_ID> -n challenge-namespace -o jsonpath='{.spec.security}'

# Review mounted volumes
kubectl get instance <INSTANCE_ID> -n challenge-namespace -o jsonpath='{.spec.volumes}'

# Check network configuration
kubectl get instance <INSTANCE_ID> -n challenge-namespace -o jsonpath='{.spec.network}'
```

### Containment Actions

#### 1. Quarantine Affected Resources
```bash
# Move challenge namespace to quarantine
kubectl label namespace challenge-namespace quarantine=true --overwrite

# Delete all pods in challenge namespace
kubectl delete pods -n challenge-namespace --all --force --grace-period=0
```

#### 2. Revoke Compromised Credentials
```bash
# Rotate database credentials
kubectl get secret cerberus-secrets -n cerberus -o yaml | kubectl replace -f -

# Rotate Redis credentials
kubectl get secret cerberus-secrets -n cerberus -o yaml | kubectl replace -f -

# Invalidate active sessions
kubectl exec -n cerberus deploy/redis -- redis-cli FLUSHALL
```

#### 3. Notify Participants
```bash
# Get affected user/team
kubectl get instance <INSTANCE_ID> -n challenge-namespace -o jsonpath='{.spec.user_id}'

# Send notification (template)
cat <<EOF | kubectl exec -n cerberus deploy/backend -- python -c "import sys; import requests; requests.post('${DISCORD_WEBHOOK_URL}', json={'content': sys.stdin.read()})"
🚨 **Security Incident Notification**

A security incident has been detected involving challenge <CHALLENGE_ID>.
The challenge has been terminated as a precautionary measure.

Please standby for further updates.
EOF
```

### Recovery Steps

#### 1. Restore Normal Operations
```bash
# Remove emergency network policy
kubectl delete networkpolicy emergency-deny-all -n challenge-namespace

# Remove quarantine label
kubectl label namespace challenge-namespace quarantine-

# Scale up orchestrator
kubectl scale deployment/cerberus-orchestrator --replicas=1 -n cerberus
```

#### 2. Reset Challenge
```bash
# Deploy fresh challenge instance
kubectl apply -f /path/to/challenge-<CHALLENGE_ID>-instance.yaml
```

### Post-Incident Actions

1. **Root cause analysis:**
   - Review challenge container image
   - Check for known CVEs
   - Analyze escape technique

2. **Update security policies:**
   ```yaml
   # Updated security context for challenge containers
   securityContext:
     privileged: false
     readOnlyRootFilesystem: true
     allowPrivilegeEscalation: false
     capabilities:
       drop: ["ALL"]
   ```

3. **Enhance monitoring:**
   - Add Falco rules for container escape
   - Enable network policy auditing
   - Set up behavioral analysis

4. **Document lessons learned:**
   - Escape vector
   - Detection time
   - Response effectiveness
   - Recommended improvements

### Preventive Measures

1. Use gVisor or Kata Containers for stronger isolation
2. Enable Falco runtime security monitoring
3. Implement network policies for all challenge pods
4. Regular security scanning of challenge images
5. Pen testing of challenges before deployment

### Contact
- Security Team: security@cerberus.example.com
- Incident Response: ir-team@cerberus.example.com
