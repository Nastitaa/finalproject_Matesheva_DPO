from datetime import datetime
from typing import Any, Dict

from ..infra.database import DatabaseManager


class ParserStorage:
    """Хранилище для данных парсера."""

    def __init__(self):
        self.db = DatabaseManager()

    def save_exchange_rate(self, rate_data: Dict[str, Any]) -> None:
        """
        Сохраняет одну запись в историю exchange_rates.json.
        rate_data должен содержать from_currency, to_currency, rate, source.
        """
        history = self.db.load_exchange_rates_history()
        record_id = self._generate_rate_id(rate_data)
        record = {
            "id": record_id,
            "from_currency": rate_data["from_currency"],
            "to_currency": rate_data["to_currency"],
            "rate": rate_data["rate"],
            "timestamp": datetime.now().isoformat() + "Z",
            "source": rate_data["source"],
            "meta": rate_data.get("meta", {}),
        }
        history.append(record)
        if len(history) > 1000:
            history = history[-1000:]
        self.db.save_exchange_rates_history(history)

    def save_current_rates(self, rates: Dict[str, float], source: str) -> None:

        current_time = datetime.now().isoformat()
        new_pairs = {}
        for pair_key, rate in rates.items():
            new_pairs[pair_key] = {
                "rate": rate,
                "updated_at": current_time,
                "source": source,
            }

        cache = self.db.load_rates_cache()

        # Если cache не содержит 'pairs', значит это старый формат (плоский словарь)
        if "pairs" not in cache:
            # Преобразуем старый формат в новый
            old_pairs = cache if isinstance(cache, dict) else {}
            cache = {"pairs": old_pairs, "last_refresh": None}

        # Обновляем пары
        cache["pairs"].update(new_pairs)
        cache["last_refresh"] = current_time

        self.db.save_rates_cache(cache)

    def _generate_rate_id(self, rate_data: Dict[str, Any]) -> str:
        from_cur = rate_data["from_currency"]
        to_cur = rate_data["to_currency"]
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        return f"{from_cur}_{to_cur}_{timestamp}"
