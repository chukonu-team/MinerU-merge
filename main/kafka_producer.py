# kafka_reporter.py
import os
from distutils.util import strtobool

from confluent_kafka import Producer
import json
import threading
import logging

logging.basicConfig(level=logging.INFO)

# Kafka 配置（按需修改）
_KAFKA_CONF = {
    "bootstrap.servers": "121.40.125.107:30091",
    "acks": "all",
    "retries": 3,
    "linger.ms": 10,
    "compression.type": "snappy"
}

topic = "mineru-test"

_producer = None
_lock = threading.Lock()


def _get_producer():
    """单例 Producer"""
    global _producer
    if _producer is None:
        with _lock:
            if _producer is None:
                _producer = Producer(_KAFKA_CONF)
    return _producer


def _delivery_report(err, msg):
    if err is not None:
        logging.error(f"Kafka 发送失败: {err}")
    else:
        logging.debug(
            f"Kafka 已发送 topic={msg.topic()} "
            f"partition={msg.partition()} offset={msg.offset()}"
        )

def report_kafka(data: dict, key: str = None):
    """
    上报 JSON 数据到 Kafka

    :param topic: Kafka topic
    :param data: dict 类型数据
    :param key: 可选，用于保证同 key 顺序
    """
    disable = bool(strtobool(os.environ.get("DISABLE_KAFKA_REPORT", "false")))
    if disable:
        logging.info("Skip report kafka")
        return
    try:
        producer = _get_producer()

        value = json.dumps(data, ensure_ascii=False).encode("utf-8")
        key_bytes = key.encode("utf-8") if key else None

        producer.produce(
            topic=topic,
            key=key_bytes,
            value=value,
            callback=_delivery_report
        )

        # 必须调用，触发回调
        producer.poll(0)

    except Exception as e:
        # 上报失败不影响主流程
        logging.exception(f"Kafka 上报异常: {e}")
