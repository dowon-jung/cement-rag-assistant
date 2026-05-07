# 🏗 인프라 설정

## 폴더 구조

```
infra/
├── k8s/               Kubernetes 매니페스트
│   ├── app/           FastAPI Deployment
│   ├── qdrant/        Qdrant StatefulSet
│   ├── postgres/      PostgreSQL StatefulSet
│   ├── redis/         Redis Deployment
│   ├── elasticsearch/ Elasticsearch StatefulSet
│   ├── neo4j/         Neo4j StatefulSet
│   ├── kafka/         Kafka StatefulSet (KRaft)
│   ├── ollama/        Ollama Deployment
│   ├── vllm/          vLLM Deployment
│   ├── monitoring/    Prometheus + Grafana
│   ├── jaeger/        Jaeger
│   └── config/        ConfigMap / Secret
├── monitoring/        Prometheus 스크레이프 설정
├── docker-compose.yml 로컬 개발 환경
└── Dockerfile         앱 컨테이너 빌드
```

## 로컬 개발 환경 기동

```bash
cd infra

# 인프라 서비스 기동
docker-compose up -d postgres redis qdrant elasticsearch neo4j kafka

# 전체 기동 (앱 포함)
docker-compose up -d

# 상태 확인
docker-compose ps
```

## K8s 배포

```bash
cd infra/k8s

# 네임스페이스 생성
kubectl apply -f namespace.yaml

# 전체 배포
kubectl apply -f .
```

> K8s 배포 상세 가이드: [../docs/design/13_kubernetes.md](../docs/design/13_kubernetes.md)
