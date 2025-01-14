"""
Run detection module holds the RunDetector main class
"""
import logging
import sys
import time
from pathlib import Path
from queue import SimpleQueue

from rundetection.ingest import ingest
from rundetection.notifications import Notifier, Notification
from rundetection.queue_listener import Message, QueueListener
from rundetection.specifications import InstrumentSpecification

file_handler = logging.FileHandler(filename="run-detection.log")
stdout_handler = logging.StreamHandler(stream=sys.stdout)
logging.basicConfig(
    handlers=[file_handler, stdout_handler],
    format="[%(asctime)s]-%(name)s-%(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class RunDetector:
    """
    Run Detector class orchestrates the complete run detection process, from consuming messages from icat
    pre-queue, to notifying downstream
    """

    def __init__(self) -> None:
        self._message_queue: SimpleQueue[Message] = SimpleQueue()
        self._queue_listener: QueueListener = QueueListener(self._message_queue)
        self._notifier: Notifier = Notifier()

    def run(self) -> None:
        """
        Starts the run detector
        """
        logging.info("Starting RunDetector")
        self._queue_listener.run()
        while True:
            self._process_message(self._message_queue.get())
            time.sleep(0.1)

    @staticmethod
    def _map_path(path_str: str) -> Path:
        """
        The paths recieved from pre-icat queue are windows formatted and assume the archive is at \\isis. This maps
        them to the expected location of /archive
        :param path_str: The path string to map
        :return: The mapped path object
        """
        path_str = path_str.replace(r"\\isis", r"\archive") if path_str.startswith(r"\\isis") else path_str
        return Path("/archive", "/".join(path_str.split("\\")))

    def _process_message(self, message: Message) -> None:
        logger.info("Processing message: %s", message)
        try:
            data_path = self._map_path(message.value)
            metadata = ingest(data_path)
            specification = InstrumentSpecification(metadata.instrument)

            if specification.verify(metadata):
                notification = Notification(metadata.to_json_string())
                self._notifier.notify(notification)
            else:
                logger.info("Specificaiton not met, skipping file: %s", metadata)
        # pylint: disable = broad-except
        except Exception:
            logger.exception("Problem processing message: %s", message.value)

        message.processed = True
        self._queue_listener.acknowledge(message)


def main(archive_path: str = "/archive") -> None:
    """
    run-detection entrypoint.
    :arg archive_path: Added purely for testing purposes, but should also be potentially useful.
    :return: None
    """
    # Check that the archive can be accessed
    if Path(archive_path, "NDXALF").exists():
        logger.info("The archive has been mounted correctly, and can be accessed.")
    else:
        logger.error("The archive has not been mounted correctly, and cannot be accessed.")

    logger.info("Starting run detection")
    run_detector = RunDetector()
    run_detector.run()


if __name__ == "__main__":
    main()
