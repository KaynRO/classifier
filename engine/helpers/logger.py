import logging, os, sys, colorama
from colorama import Fore, Style


colorama.init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: Fore.BLUE,
        logging.INFO: Fore.CYAN,
        25: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }


    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno)
        levelname = record.levelname.center(8)
        record.levelname = f"{color}{levelname}{Style.RESET_ALL}"
        return super().format(record)


class Logger:
    def __init__(self, name: str) -> None:
        logging.addLevelName(25, "SUCCESS")
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.name = name

        self.buffering_enabled = False
        self.log_buffer = []

        # Ensure log directory exists
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_filename = "domain-classification.log"
        log_path = os.path.join(log_dir, log_filename)

        # Configure file and console formatters
        file_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S"
        )
        console_formatter = ColoredFormatter(
            f"{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - %(levelname)s - {Fore.WHITE}%(message)s{Style.RESET_ALL}",
            "%Y-%m-%d %H:%M:%S",
        )

        # Attach handlers only once per logger instance
        if not self.logger.handlers:
            file_handler = logging.FileHandler(log_path)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)


    def enable_buffering(self) -> None:
        self.buffering_enabled = True
        self.log_buffer = []


    def disable_buffering(self) -> None:
        self.buffering_enabled = False


    def flush_buffer(self) -> None:
        if self.log_buffer:
            for level, message in self.log_buffer:
                if level == "INFO":
                    self.logger.info(message)
                elif level == "SUCCESS":
                    self.logger.log(25, message)
                elif level == "DEBUG":
                    self.logger.debug(message)
                elif level == "WARNING":
                    self.logger.warning(message)
                elif level == "ERROR":
                    self.logger.error(message)

        self.log_buffer = []
        self.buffering_enabled = False


    def info(self, message: str) -> None:
        if self.buffering_enabled:
            self.log_buffer.append(("INFO", message))
        elif self.logger.isEnabledFor(logging.INFO):
            self.logger.info(message)


    def success(self, message: str) -> None:
        if self.buffering_enabled:
            self.log_buffer.append(("SUCCESS", message))
        elif self.logger.isEnabledFor(25):
            self.logger.log(25, message)


    def debug(self, message: str) -> None:
        if self.buffering_enabled:
            self.log_buffer.append(("DEBUG", message))
        elif self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(message)


    def warn(self, message: str) -> None:
        if self.buffering_enabled:
            self.log_buffer.append(("WARNING", message))
        else:
            self.logger.warning(message)


    def warning(self, message: str) -> None:
        if self.buffering_enabled:
            self.log_buffer.append(("WARNING", message))
        else:
            self.logger.warning(message)


    def error(self, message: str) -> None:
        if self.buffering_enabled:
            self.log_buffer.append(("ERROR", message))
        else:
            self.logger.error(message)

