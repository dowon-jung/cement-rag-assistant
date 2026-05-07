"""
agent 서비스 진입점
LangGraph Multi-Agent 워크플로우를 실행하는 내부 FastAPI 서버.
"""
from fastapi import FastAPI

app = FastAPI(title="Agent Service", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "agent"}
