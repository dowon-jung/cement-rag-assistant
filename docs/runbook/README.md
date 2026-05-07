# 📋 Runbook

단계별 실행 가이드 모음입니다.
각 Phase를 완료한 후 해당 Runbook을 따라 실행하고 결과를 확인하세요.

## 목록

| 파일 | 대상 Phase | 내용 |
|------|-----------|------|
| [01_setup_verify.md](01_setup_verify.md) | Phase 1~2 | 환경 세팅 및 수집기 동작 확인 |

---

## 공통 사전 조건

```bash
# 레포 클론
git clone https://github.com/dowon-jung/cement-rag-assistant.git
cd cement-rag-assistant

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 API 키 입력

# Python 패키지 설치
pip install -e ".[dev]"
```

---

## 체크포인트 기록 방법

각 Step 실행 후 아래 형식으로 `daily/` 로그에 기록하세요.

```
- [x] Step 1 — Docker Compose 기동 확인 (2026-05-08 완료)
- [ ] Step 2 — DB 초기화 (미완료, 오류 내용: ...)
```
