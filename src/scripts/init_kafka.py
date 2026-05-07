"""
Kafka 토픽 초기화 스크립트
실행: python scripts/init_kafka.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
from shared.config import settings

# 7일 = 604,800,000ms / 3일 = 259,200,000ms / 14일 = 1,209,600,000ms / 30일 = 2,592,000,000ms
TOPICS = [
    NewTopic(
        name="market.raw",
        num_partitions=3,
        replication_factor=1,
        topic_configs={"retention.ms": "604800000"},       # 7일
    ),
    NewTopic(
        name="news.raw",
        num_partitions=3,
        replication_factor=1,
        topic_configs={"retention.ms": "604800000"},       # 7일
    ),
    NewTopic(
        name="weather.raw",
        num_partitions=3,
        replication_factor=1,
        topic_configs={"retention.ms": "259200000"},       # 3일
    ),
    NewTopic(
        name="erp.updated",
        num_partitions=1,
        replication_factor=1,
        topic_configs={"retention.ms": "1209600000"},      # 14일
    ),
    NewTopic(
        name="indexing.requests",
        num_partitions=5,
        replication_factor=1,
        topic_configs={"retention.ms": "604800000"},       # 7일
    ),
    NewTopic(
        name="indexing.results",
        num_partitions=3,
        replication_factor=1,
        topic_configs={"retention.ms": "259200000"},       # 3일
    ),
    NewTopic(
        name="llm.requests",
        num_partitions=5,
        replication_factor=1,
        topic_configs={"retention.ms": "604800000"},       # 7일
    ),
    NewTopic(
        name="llm.results",
        num_partitions=5,
        replication_factor=1,
        topic_configs={"retention.ms": "259200000"},       # 3일
    ),
    NewTopic(
        name="dlq.errors",
        num_partitions=3,
        replication_factor=1,
        topic_configs={"retention.ms": "2592000000"},      # 30일
    ),
]


def init_kafka():
    admin = KafkaAdminClient(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        client_id="cement-rag-init",
    )

    for topic in TOPICS:
        try:
            admin.create_topics([topic], validate_only=False)
            print(f"  [OK] 생성 완료: {topic.name} (파티션 {topic.num_partitions}개)")
        except TopicAlreadyExistsError:
            print(f"  [SKIP] 이미 존재함: {topic.name}")
        except Exception as e:
            print(f"  [ERROR] {topic.name}: {e}")

    admin.close()

    print(f"\nKafka 토픽 초기화 완료")
    print(f"총 토픽: {len(TOPICS)}개")


if __name__ == "__main__":
    print("Kafka 토픽 초기화 중...")
    init_kafka()
