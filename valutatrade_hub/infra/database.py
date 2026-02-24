import json
import os
from typing import Any, Dict, List

from .settings import SettingsLoader


class DatabaseManager:
    """Синглтон для работы с JSON-файлами данных."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._settings = SettingsLoader()
            cls._instance._data_dir = cls._instance._settings.get("data_dir", "data")
            cls._instance._ensure_data_dir()
        return cls._instance

    def _ensure_data_dir(self):
        os.makedirs(self._data_dir, exist_ok=True)

    def _path(self, filename: str) -> str:
        return os.path.join(self._data_dir, filename)

    def _load_json(self, filename: str, default: Any = None) -> Any:
        path = self._path(filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default if default is not None else []

    def _save_json(self, filename: str, data: Any) -> None:
        path = self._path(filename)
        # Атомарная запись через временный файл
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)

    # Пользователи
    def load_users(self) -> List[dict]:
        return self._load_json("users.json", [])

    def save_users(self, users: List[dict]) -> None:
        self._save_json("users.json", users)

    # Портфели
    def load_portfolios(self) -> List[dict]:
        return self._load_json("portfolios.json", [])

    def save_portfolios(self, portfolios: List[dict]) -> None:
        self._save_json("portfolios.json", portfolios)

    # Курсы (кэш для Core)
    def load_rates_cache(self) -> Dict[str, Any]:
        return self._load_json("rates.json", {"pairs": {}, "last_refresh": None})

    def save_rates_cache(self, data: Dict[str, Any]) -> None:
        """Сохраняет rates.json."""
        self._save_json("rates.json", data)

    # Исторические данные (exchange_rates.json)
    def load_exchange_rates_history(self) -> List[Dict[str, Any]]:
        """Загружает историю курсов (массив записей)."""
        return self._load_json("exchange_rates.json", [])

    def save_exchange_rates_history(self, history: List[Dict[str, Any]]) -> None:
        """Сохраняет историю курсов."""
        self._save_json("exchange_rates.json", history)
