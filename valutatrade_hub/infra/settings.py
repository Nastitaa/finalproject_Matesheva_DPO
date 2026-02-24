import json
import os
from typing import Any


class SettingsLoader:
    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """Загружает конфигурацию из config.json (в корне проекта)."""
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
        config_path = os.path.abspath(config_path)
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        except json.JSONDecodeError:
            raise RuntimeError("Config file is malformed")

    def get(self, key: str, default: Any = None) -> Any:
        """Возвращает значение ключа конфигурации или default."""
        return self._config.get(key, default)

    def reload(self):
        """Перезагружает конфигурацию из файла."""
        self._load_config()
