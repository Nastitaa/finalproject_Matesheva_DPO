import logging
import os
from logging.handlers import RotatingFileHandler

from .infra.settings import SettingsLoader

# Глобальный флаг, чтобы не настраивать корневой логгер повторно
_logging_configured = False


def setup_logging():
    """
    Настраивает корневой логгер и файловый обработчик с ротацией.
    Возвращает корневой логгер.
    """
    global _logging_configured
    if _logging_configured:
        return logging.getLogger()

    settings = SettingsLoader()
    log_dir = settings.get("logs_dir", "logs")
    log_file = settings.get("log_file", "valutatrade.log")
    log_level = settings.get("log_level", "INFO")
    max_bytes = settings.get("log_max_bytes", 1048576)
    backup_count = settings.get("log_backup_count", 3)

    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Если уже есть обработчики, не добавляем повторно
    if root_logger.handlers:
        _logging_configured = True
        return root_logger

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
    )

    handler = RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Можно добавить консольный вывод для отладки (раскомментировать при необходимости)
    # console = logging.StreamHandler()
    # console.setFormatter(formatter)
    # root_logger.addHandler(console)

    _logging_configured = True
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Возвращает логгер с указанным именем, гарантируя, что корневой логгер настроен.
    """
    if not _logging_configured:
        setup_logging()
    return logging.getLogger(name)
