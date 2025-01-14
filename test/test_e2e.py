"""
End-to-end tests
"""
# pylint: disable=redefined-outer-name, no-name-in-module
import unittest

import pytest
from confluent_kafka import Consumer
from confluent_kafka.admin import AdminClient
from confluent_kafka.cimpl import NewTopic, KafkaError
from stomp import Connection


@pytest.fixture
def amq_connection() -> Connection:
    """
    Setup and return stomp connection
    :return: stomp connection
    """
    conn = Connection()
    conn.connect("admin", "admin")
    return conn


@pytest.fixture
def kafka_consumer() -> Consumer:
    """
    Setup and return the kafka consumer
    :return: kafka consumer
    """
    admin_client = AdminClient({"bootstrap.servers": "localhost:29092"})
    topic = NewTopic("detected-runs", 1, 1)
    admin_client.create_topics([topic])
    consumer = Consumer({"bootstrap.servers": "localhost:29092", "group.id": "test", "auto.offset.reset": "earliest"})
    consumer.subscribe(["detected-runs"])
    return consumer


def test_end_to_end(amq_connection: Connection, kafka_consumer: Consumer) -> None:
    """
    Test message that is sent to activemq is processed and arrives at kafka instance
    :return: None
    """

    amq_connection.send("Interactive-Reduction", r"\\isis\1600007\IMAT00004217.nxs")
    amq_connection.send("Interactive-Reduction", r"\\isis\1510111\ENGINX00241391.nxs")
    amq_connection.send("Interactive-Reduction", r"\\isis\1920302\ALF82301.nxs")

    received = []
    for _ in range(60):
        if len(received) >= 2:
            break
        msg = kafka_consumer.poll(timeout=1.0)
        if msg is None:
            continue
        try:
            if msg.error():
                pytest.fail(f"Failed to consume from broker: {msg.error()}")
            received.append(msg.value())

        except KafkaError as exc:
            kafka_consumer.close()
            pytest.fail("Problem with kafka consumer", exc)
    else:
        kafka_consumer.close()
        pytest.fail("No message could be consumed")

    assert received == [
        b'{"run_number": 241391, "instrument": "ENGINX", "experiment_title": "CeO2 4 x'
        b' 4 x 15", "experiment_number": "1510111", "filepath": "/archive/1510111/ENGINX00241391.nxs"}',
        b'{"run_number": 82301, "instrument": "ALF", "experiment_title": "YbCl3 rot=0"'
        b', "experiment_number": "1920302", "filepath": "/archive/1920302/ALF82301.nxs"}',
    ]


if __name__ == "__main__":
    unittest.main()
