import logging

"""
Logger class
"""


class LoggerManager:
    """
    Initalize the logging instance

    Returns:
    - The logger associated with this module
    """

    def __init__(self, name: str = "Fuzzer", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Avoid duplicate handlers if logger already has one
        if not self.logger.hasHandlers():
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def get_logger(self):
        return self.logger
