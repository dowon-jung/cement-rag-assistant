# 13. Kubernetes 배포 설계

## 1. 배포 환경

| 단계 | 환경 | 용도 |
|------|------|------|
| 개발 | Docker Compose | 로컬 개발 |
| 스테이징 | minikube | K8s 매니페스트 검증 |
| 프로덕션 | EKS / GKE / 사내 K8s | 실제 운영 |

---

## 2. 네임스페이스 구조

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: cement-rag
  labels:
    app: cement-rag-assistant
```

---

## 3. 리소스 구성 개요

| 리소스 | 종류 | 이유 |
|--------|------|------|
| FastAPI App | Deployment + HPA | Stateless, 트래픽 기반 스케일 아웃 |
| Kafka Consumer | Deployment + KEDA | Lag 기반 스케일 아웃 |
| Qdrant | StatefulSet | 영속 데이터, 안정적 식별자 필요 |
| PostgreSQL | StatefulSet | 영속 데이터 |
| Neo4j | StatefulSet | 영속 데이터 |
| Kafka | StatefulSet | 영속 데이터 (KRaft 모드) |
| Elasticsearch | StatefulSet | 영속 데이터, nori 플러그인 |
| Ollama | Deployment | GPU 노드 affinity |
| vLLM | Deployment | GPU 노드 affinity, OpenAI 호환 |
| Prometheus | StatefulSet | TSDB |
| Grafana | Deployment | 설정만 ConfigMap |
| Jaeger | Deployment | 트레이스 (옵션 영속화) |

---

## 4. FastAPI Deployment

```yaml
# k8s/app/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cement-rag-app
  namespace: cement-rag
spec:
  replicas: 2
  selector:
    matchLabels:
      app: cement-rag-app
  template:
    metadata:
      labels:
        app: cement-rag-app
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
        - name: app
          image: harbor.internal/cement-rag/app:v0.1.0
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: cement-rag-config
            - secretRef:
                name: cement-rag-secrets
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 2000m
              memory: 2Gi
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
            initialDelaySeconds: 5
            periodSeconds: 5
```

---

## 5. HPA (수평 스케일 아웃)

### FastAPI App — CPU 기반

```yaml
# k8s/app/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: cement-rag-app-hpa
  namespace: cement-rag
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: cement-rag-app
  minReplicas: 2
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
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Percent
          value: 100
          periodSeconds: 30
```

### Kafka Consumer — KEDA 기반 (lag 기준)

```yaml
# k8s/kafka/scaledobject.yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: indexing-consumer-scaler
  namespace: cement-rag
spec:
  scaleTargetRef:
    name: indexing-consumer
  pollingInterval: 30
  cooldownPeriod: 300
  minReplicaCount: 1
  maxReplicaCount: 10
  triggers:
    - type: kafka
      metadata:
        bootstrapServers: kafka:9092
        consumerGroup: indexing-workers
        topic: indexing.requests
        lagThreshold: "100"
```

> Consumer lag이 100 초과 시 Pod를 자동으로 늘림. 확장성 요구사항을 충족.

---

## 6. StatefulSet — Qdrant 예시

```yaml
# k8s/qdrant/statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: qdrant
  namespace: cement-rag
spec:
  serviceName: qdrant
  replicas: 1
  selector:
    matchLabels:
      app: qdrant
  template:
    metadata:
      labels:
        app: qdrant
    spec:
      containers:
        - name: qdrant
          image: harbor.internal/cement-rag/qdrant:v1.12.0
          ports:
            - containerPort: 6333
            - containerPort: 6334
          volumeMounts:
            - name: data
              mountPath: /qdrant/storage
          resources:
            requests:
              cpu: 1000m
              memory: 4Gi
            limits:
              cpu: 4000m
              memory: 8Gi
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: standard
        resources:
          requests:
            storage: 50Gi
```

---

## 7. Kafka StatefulSet (KRaft 모드)

```yaml
# k8s/kafka/statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: kafka
  namespace: cement-rag
spec:
  serviceName: kafka-headless
  replicas: 3
  selector:
    matchLabels:
      app: kafka
  template:
    spec:
      containers:
        - name: kafka
          image: harbor.internal/cement-rag/kafka:7.5.0
          ports:
            - containerPort: 9092
            - containerPort: 9093
          env:
            - name: KAFKA_NODE_ID
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
            - name: KAFKA_PROCESS_ROLES
              value: "broker,controller"
            - name: KAFKA_CONTROLLER_QUORUM_VOTERS
              value: "0@kafka-0.kafka-headless:9093,1@kafka-1.kafka-headless:9093,2@kafka-2.kafka-headless:9093"
          volumeMounts:
            - name: data
              mountPath: /var/lib/kafka/data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 100Gi
```

---

## 8. Ollama Deployment (GPU 노드)

```yaml
# k8s/ollama/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama
  namespace: cement-rag
spec:
  replicas: 1
  template:
    spec:
      nodeSelector:
        accelerator: gpu          # GPU 노드만 스케줄
      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule
      containers:
        - name: ollama
          image: harbor.internal/cement-rag/ollama:latest
          ports:
            - containerPort: 11434
          resources:
            requests:
              cpu: 2000m
              memory: 8Gi
              nvidia.com/gpu: 1
            limits:
              nvidia.com/gpu: 1
          volumeMounts:
            - name: models
              mountPath: /root/.ollama
      volumes:
        - name: models
          persistentVolumeClaim:
            claimName: ollama-models
```

---

## 9. vLLM Deployment (GPU 노드)

```yaml
# k8s/vllm/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm
  namespace: cement-rag
spec:
  replicas: 1
  template:
    spec:
      nodeSelector:
        accelerator: gpu
      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule
      containers:
        - name: vllm
          image: harbor.internal/cement-rag/vllm:latest
          args:
            - "--model"
            - "/models/gemma2-9b"
            - "--host"
            - "0.0.0.0"
            - "--port"
            - "8001"
            - "--gpu-memory-utilization"
            - "0.9"
            - "--max-model-len"
            - "4096"
          ports:
            - containerPort: 8001
          resources:
            requests:
              cpu: 4000m
              memory: 16Gi
              nvidia.com/gpu: 1
            limits:
              nvidia.com/gpu: 1
          volumeMounts:
            - name: models
              mountPath: /models
      volumes:
        - name: models
          persistentVolumeClaim:
            claimName: vllm-models
```

> LLM_BACKEND=vllm 시 VLLM_HOST 환경변수로 이 서비스를 가리킵니다.
> Ollama와 vLLM 중 환경에 맞게 하나만 기동하거나 둘 다 기동 후 LLM_BACKEND로 전환할 수 있습니다.

## 10. Service 정의

```yaml
# k8s/app/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: cement-rag-app
  namespace: cement-rag
spec:
  selector:
    app: cement-rag-app
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP

---
# Headless Service for StatefulSet
apiVersion: v1
kind: Service
metadata:
  name: kafka-headless
  namespace: cement-rag
spec:
  selector:
    app: kafka
  ports:
    - port: 9092
      name: broker
  clusterIP: None
```

---

## 11. ConfigMap 및 Secret

### ConfigMap (설정값)

```yaml
# k8s/config/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cement-rag-config
  namespace: cement-rag
data:
  LLM_BACKEND: "local"
  AIRGAP_MODE: "false"
  POSTGRES_HOST: "postgres"
  POSTGRES_PORT: "5432"
  REDIS_HOST: "redis"
  QDRANT_HOST: "qdrant"
  NEO4J_URI: "bolt://neo4j:7687"
  KAFKA_BOOTSTRAP_SERVERS: "kafka-headless:9092"
  OLLAMA_HOST: "http://ollama:11434"
```

### Secret (민감 정보)

```bash
# Secret은 매니페스트 직접 작성 X, kubectl로 생성
kubectl create secret generic cement-rag-secrets \
  --namespace=cement-rag \
  --from-literal=BOK_API_KEY=xxxx \
  --from-literal=NAVER_CLIENT_ID=xxxx \
  --from-literal=NAVER_CLIENT_SECRET=xxxx \
  --from-literal=WEATHER_API_KEY=xxxx \
  --from-literal=POSTGRES_PASSWORD=xxxx \
  --from-literal=NEO4J_PASSWORD=xxxx
```

> 프로덕션에서는 **Sealed Secrets** 또는 **External Secrets Operator** + Vault 권장.

---

## 12. Ingress

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: cement-rag-ingress
  namespace: cement-rag
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-buffering: "off"   # SSE 스트리밍용
    nginx.ingress.kubernetes.io/proxy-read-timeout: "600"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - cement-rag.example.com
      secretName: cement-rag-tls
  rules:
    - host: cement-rag.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: cement-rag-app
                port:
                  number: 80
```

---

## 13. PersistentVolume 전략

| 서비스 | 용도 | 크기 | StorageClass |
|--------|------|------|--------------|
| PostgreSQL | DB 데이터 | 50Gi | standard |
| Elasticsearch | 인덱스 데이터 | 30Gi | standard |
| Qdrant | 벡터 인덱스 | 50Gi | standard |
| Neo4j | 그래프 데이터 | 20Gi | standard |
| Kafka | 메시지 로그 | 100Gi (3개) | fast-ssd |
| Ollama | 모델 파일 | 30Gi | standard |
| Prometheus | 메트릭 TSDB | 20Gi | standard |

---

## 14. 배포 순서

```bash
# 1. 네임스페이스
kubectl apply -f k8s/namespace.yaml

# 2. ConfigMap, Secret
kubectl apply -f k8s/config/

# 3. 인프라 (StatefulSet)
kubectl apply -f k8s/postgres/
kubectl apply -f k8s/redis/
kubectl apply -f k8s/elasticsearch/
kubectl apply -f k8s/qdrant/
kubectl apply -f k8s/neo4j/
kubectl apply -f k8s/kafka/

# 4. Topic 초기화
kubectl exec -it kafka-0 -- /bin/bash
# 또는 init job으로 처리

# 5. LLM 서빙
kubectl apply -f k8s/ollama/

# 6. 앱
kubectl apply -f k8s/app/

# 7. 모니터링
kubectl apply -f k8s/monitoring/

# 8. Ingress
kubectl apply -f k8s/ingress.yaml
```

---

## 15. 롤링 업데이트 전략

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1                    # 최대 1개 추가 Pod
      maxUnavailable: 0              # 다운타임 0
  minReadySeconds: 10                # Pod 안정화 대기
```

### 롤백
```bash
kubectl rollout undo deployment/cement-rag-app -n cement-rag
kubectl rollout history deployment/cement-rag-app -n cement-rag
```

---

## 16. 배포 검증 체크리스트

- [ ] 모든 Pod Running 상태 확인 (`kubectl get pods -n cement-rag`)
- [ ] 헬스체크 `/health` 200 응답
- [ ] FastAPI `/docs` 접근 가능
- [ ] Grafana 대시보드 메트릭 수신 확인
- [ ] Kafka Consumer가 메시지 처리하는지 확인
- [ ] HPA 동작 확인 (부하 테스트)
- [ ] Pod 강제 종료 시 자동 복구 확인
- [ ] StatefulSet 데이터 영속성 확인 (Pod 재시작 후 데이터 유지)
- [ ] Ingress TLS 인증서 정상 발급
- [ ] SSE 스트리밍 응답 정상 동작 (nginx 버퍼링 off)

---

## 17. 부하 테스트 시나리오

```bash
# locust로 K8s 환경에 부하
locust -f locustfile.py \
  --host=https://cement-rag.example.com \
  --users 100 \
  --spawn-rate 10

# HPA 동작 확인
kubectl get hpa -n cement-rag -w
kubectl get pods -n cement-rag -w
```

목표:
- 동시 사용자 100명 → FastAPI Pod 2개 → 5개로 스케일 아웃
- Kafka lag 1000 초과 → Consumer Pod 1개 → 3개로 스케일 아웃
- 트래픽 안정 후 5분 내 원래대로 축소
