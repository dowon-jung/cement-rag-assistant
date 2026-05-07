"""
indexer 서비스 진입점
Kafka indexing.requests 토픽을 구독하여 문서를 벡터 DB에 적재한다.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


async def main():
    logger.info("Indexer 서비스 시작")
    # TODO: Phase 3에서 구현


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    asyncio.run(main())
