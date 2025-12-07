import logging


class ColorStreamHandler(logging.Handler):
    """
    A logging handler that outputs colored logs to the console.
    """

    COLOR_CODES = {
        "DEBUG": "\033[94m",  # Blue
        "INFO": "\033[92m",  # Green
        "WARNING": "\033[93m",  # Yellow
        "ERROR": "\033[91m",  # Red
        "CRITICAL": "\033[95m",  # Magenta
    }
    RESET_CODE = "\033[0m"

    def emit(self, record: logging.LogRecord) -> None:
        color_code = self.COLOR_CODES.get(record.levelname, self.RESET_CODE)
        message = self.format(record)
        colored_message = f"{color_code}{message}{self.RESET_CODE}"
        print(colored_message)


logger = logging.getLogger("MANAGER")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("[%(name)7s] - [%(levelname)7s] - %(message)s")
handler = ColorStreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)
