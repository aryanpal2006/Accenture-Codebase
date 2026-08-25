"""
Kubernetes Deployment Manifests
Scale the triage system to multiple replicas across a cluster.

Place these in a k8s/ directory and deploy with:
  kubectl apply -f k8s/
"""

# ============================================================================
# k8s/namespace.yaml
# ============================================================================

apiVersion: v1
kind: Namespace
metadata:
  name: triage
  labels:
    name: triage

---

# ============================================================================
# k8s/configmap.yaml
# ============================================================================

apiVersion: v1
kind: ConfigMap
metadata:
  name: triage-config
  namespace: triage
data:
  DATABASE_URL: "postgresql://triage_user:triage_secure_pass_2024@postgres-service:5432/triage_db"
  ENVIRONMENT: "production"
  LOG_LEVEL: "INFO"

---

# ============================================================================
# k8s/secret.yaml
# ============================================================================

apiVersion: v1
kind: Secret
metadata:
  name: triage-db-secret
  namespace: triage
type: Opaque
stringData:
  POSTGRES_USER: "triage_user"
  POSTGRES_PASSWORD: "triage_secure_pass_2024"  # CHANGE THIS!
  POSTGRES_DB: "triage_db"

---

# ============================================================================
# k8s/postgres-statefulset.yaml
# Database Persistence Layer
# ============================================================================

apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: triage
spec:
  serviceName: postgres-service
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        ports:
        - containerPort: 5432
          name: postgres
        env:
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: triage-db-secret
              key: POSTGRES_USER
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: triage-db-secret
              key: POSTGRES_PASSWORD
        - name: POSTGRES_DB
          valueFrom:
            secretKeyRef:
              name: triage-db-secret
              key: POSTGRES_DB
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        livenessProbe:
          exec:
            command:
            - /bin/sh
            - -c
            - pg_isready -U $POSTGRES_USER
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc

---

# ============================================================================
# k8s/postgres-pvc.yaml
# Database Storage
# ============================================================================

apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: triage
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
  storageClassName: standard

---

# ============================================================================
# k8s/postgres-service.yaml
# Database Service (Internal)
# ============================================================================

apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: triage
spec:
  clusterIP: None  # Headless service for StatefulSet
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432

---

# ============================================================================
# k8s/triage-api-deployment.yaml
# API Application (Scalable)
# ============================================================================

apiVersion: apps/v1
kind: Deployment
metadata:
  name: triage-api
  namespace: triage
spec:
  replicas: 3  # Start with 3, scale based on load
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: triage-api
  template:
    metadata:
      labels:
        app: triage-api
    spec:
      serviceAccountName: triage-api
      containers:
      - name: api
        image: triage-api:latest  # Build and push to registry first
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: DATABASE_URL
          valueFrom:
            configMapKeyRef:
              name: triage-config
              key: DATABASE_URL
        - name: ENVIRONMENT
          valueFrom:
            configMapKeyRef:
              name: triage-config
              key: ENVIRONMENT
        - name: LOG_LEVEL
          valueFrom:
            configMapKeyRef:
              name: triage-config
              key: LOG_LEVEL
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5

---

# ============================================================================
# k8s/triage-api-service.yaml
# API Service (Load Balanced)
# ============================================================================

apiVersion: v1
kind: Service
metadata:
  name: triage-api-service
  namespace: triage
spec:
  type: LoadBalancer
  selector:
    app: triage-api
  ports:
  - port: 80
    targetPort: 8000
    name: http

---

# ============================================================================
# k8s/triage-hpa.yaml
# Horizontal Pod Autoscaling
# ============================================================================

apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: triage-api-hpa
  namespace: triage
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: triage-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80

---

# ============================================================================
# k8s/triage-api-rbac.yaml
# Service Account & Permissions
# ============================================================================

apiVersion: v1
kind: ServiceAccount
metadata:
  name: triage-api
  namespace: triage

---

apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: triage-api-role
  namespace: triage
rules:
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list", "watch"]

---

apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: triage-api-rolebinding
  namespace: triage
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: triage-api-role
subjects:
- kind: ServiceAccount
  name: triage-api
  namespace: triage

---

# ============================================================================
# k8s/ingress.yaml
# External Access (HTTPS)
# ============================================================================

apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: triage-ingress
  namespace: triage
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - triage-api.yourhospital.com
    secretName: triage-tls
  rules:
  - host: triage-api.yourhospital.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: triage-api-service
            port:
              number: 80

---

# ============================================================================
# k8s/network-policy.yaml
# Security: Restrict Traffic
# ============================================================================

apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: triage-network-policy
  namespace: triage
spec:
  podSelector:
    matchLabels:
      app: triage-api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 53  # DNS

---

# ============================================================================
# k8s/pod-security-policy.yaml
# Security: Pod Constraints
# ============================================================================

apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: triage-psp
spec:
  privileged: false
  allowPrivilegeEscalation: false
  requiredDropCapabilities:
    - ALL
  volumes:
    - 'configMap'
    - 'emptyDir'
    - 'projected'
    - 'secret'
    - 'downwardAPI'
    - 'persistentVolumeClaim'
  runAsUser:
    rule: 'MustRunAsNonRoot'
  seLinux:
    rule: 'MustRunAs'
    seLinuxOptions:
      level: "s0:c123,c456"
  readOnlyRootFilesystem: true

---

# ============================================================================
# Deployment Instructions
# ============================================================================

"""
KUBERNETES DEPLOYMENT GUIDE

1. Build and Push Docker Image
   docker build -t your-registry/triage-api:latest .
   docker push your-registry/triage-api:latest

2. Update image in triage-api-deployment.yaml:
   image: your-registry/triage-api:latest

3. Change database password in secret.yaml before deploying!
   POSTGRES_PASSWORD: "your-secure-password"

4. Deploy to cluster:
   kubectl create namespace triage  # If not exists
   kubectl apply -f k8s/

5. Verify deployment:
   kubectl get pods -n triage
   kubectl get svc -n triage
   kubectl logs -n triage deployment/triage-api

6. Wait for LoadBalancer IP (if using cloud provider):
   kubectl get svc -n triage triage-api-service --watch

7. Test API:
   curl http://LOADBALANCER_IP/health

8. Scale replicas:
   kubectl scale deployment triage-api -n triage --replicas=5

9. Monitor autoscaling:
   kubectl get hpa -n triage -w

10. View logs:
    kubectl logs -n triage -f deployment/triage-api

CLEANUP
-------
kubectl delete namespace triage

PRODUCTION CHECKLIST
--------------------
[ ] Database password changed
[ ] Image pulled from secure registry
[ ] TLS certificate configured (cert-manager)
[ ] Network policies enforced
[ ] Pod security policies applied
[ ] Resource limits/requests set
[ ] Logging/monitoring configured
[ ] Backup strategy in place
[ ] HIPAA compliance reviewed
[ ] Ingress with HTTPS enabled
"""
