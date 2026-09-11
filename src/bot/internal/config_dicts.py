import logging.config
import sys
from datetime import datetime
from logging import Formatter
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path

from pydantic_settings import SettingsConfigDict


class CustomFormatter(Formatter):
    def formatTime(self, record, datefmt=None):
        ct = datetime.fromtimestamp(record.created).astimezone()
        if datefmt:
            base_time = ct.strftime("%d.%m.%Y %H:%M:%S")
            msecs = f"{int(record.msecs):03d}"
            tz = ct.strftime("%z")
            return f"{base_time}.{msecs}{tz}"
        else:
            return super().formatTime(record, datefmt)


def initial_setup(app_name: str) -> tuple[QueueListener, ...]:
    Path("logs").mkdir(parents=True, exist_ok=True)
    Path("photos").mkdir(parents=True, exist_ok=True)
    logging_config = get_logging_config(app_name)
    logging.config.dictConfig(logging_config)
    listeners = []
    for name in ("file_queue", "console_queue"):
        handler = logging.getHandlerByName(name)
        if not isinstance(handler, QueueHandler) or handler.listener is None:
            raise RuntimeError(f"Logging queue {name} has no listener")
        handler.listener.start()
        listeners.append(handler.listener)
    return tuple(listeners)


main_template = {
    "format": "%(asctime)s | %(message)s",
    "datefmt": "%d.%m.%Y %H:%M:%S%z",
}
error_template = {
    "format": "%(asctime)s [%(levelname)8s] [%(module)s:%(funcName)s:%(lineno)d] %(message)s",
    "datefmt": "%d.%m.%Y %H:%M:%S%z",
}


def get_logging_config(app_name: str):
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "main": {
                "()": CustomFormatter,
                "format": main_template["format"],
                "datefmt": main_template["datefmt"],
            },
            "errors": {
                "()": CustomFormatter,
                "format": error_template["format"],
                "datefmt": error_template["datefmt"],
            },
        },
        "handlers": {
            # Separate consumers keep a blocked terminal from delaying file logs.
            "console_queue": {
                "class": "logging.handlers.QueueHandler",
                "handlers": ["stdout", "stderr"],
                "respect_handler_level": True,
            },
            "file_queue": {
                "class": "logging.handlers.QueueHandler",
                "handlers": ["file"],
                "respect_handler_level": True,
            },
            "stdout": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "main",
                "stream": sys.stdout,
            },
            "stderr": {
                "class": "logging.StreamHandler",
                "level": "WARNING",
                "formatter": "errors",
                "stream": sys.stderr,
            },
            "file": {
                "()": RotatingFileHandler,
                "level": "INFO",
                "formatter": "main",
                "filename": f"logs/{app_name}.log",
                "maxBytes": 50000000,
                "backupCount": 3,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "root": {
                "level": "DEBUG",
                "handlers": ["file_queue", "console_queue"],
            },
        },
    }


def assign_config_dict(prefix: str = "") -> SettingsConfigDict:
    return SettingsConfigDict(
        env_prefix=prefix,
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
    )
