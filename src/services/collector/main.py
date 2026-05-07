"""
collector 서비스 진입점
수집 작업을 스케줄링하고 Kafka로 이벤트를 발행한다.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


async def main():
    logger.info("Collector 서비스 시작")
    # TODO: Phase 3에서 구현


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    asyncio.run(main())
