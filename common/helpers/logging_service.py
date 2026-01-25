"""House logging service that simplifies logging for all classes"""
import logging


class LoggingService:
    """House logging service that simplifies logging for all classes"""
    @staticmethod
    def get_logger(class_name: str) -> logging.Logger:
        """Returns initialized logger with correct log structure"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        return logging.getLogger(class_name)