from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from shared.config import settings

app = FastAPI(
    title="시멘트 제조업 특화 Hybrid RAG 어시스턴트",
    description="실시간 API + 문서 RAG + 지식 그래프 기반 AI 어시스턴트",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Prometheus 메트릭 마운트
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health", tags=["system"])
async def health():
    """헬스체크 엔드포인트"""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "llm_backend": settings.llm_backend,
        "airgap_mode": settings.airgap_mode,
    }


@app.get("/", tags=["system"])
async def root():
    return {
        "message": "시멘트 제조업 특화 Hybrid RAG 어시스턴트",
        "docs": "/docs",
    }
