import time
from abc import ABC, abstractmethod
from typing import Dict, Optional

import requests

from ..core.exceptions import ApiRequestError
from .config import ParserConfig


class BaseApiClient(ABC):
    """Базовый класс для клиентов API."""

    def __init__(self, config: ParserConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "CurrencyParser/1.0", "Accept": "application/json"}
        )

    @abstractmethod
    def fetch_rates(self) -> Dict[str, float]:
        """
        Возвращает словарь вида {"BTC_USD": 59337.21, ...}
        """
        pass

    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Выполняет HTTP-запрос с повторными попытками."""
        last_error = None
        for attempt in range(self.config.REQUEST_RETRIES):
            try:
                response = self.session.get(
                    url, params=params, timeout=self.config.REQUEST_TIMEOUT
                )
                if response.status_code != 200:
                    raise ApiRequestError(
                        f"HTTP {response.status_code}: {response.text[:100]}"
                    )
                return response.json()
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt == self.config.REQUEST_RETRIES - 1:
                    raise ApiRequestError(
                        "Не удалось выполнить запрос после"
                        f"{self.config.REQUEST_RETRIES}"
                        f"попыток: {last_error}"
                    )
                time.sleep(self.config.RETRY_DELAY * (attempt + 1))
        raise ApiRequestError(f"Неизвестная ошибка при запросе к {url}")


class CoinGeckoClient(BaseApiClient):
    """Клиент для CoinGecko API (без ключа)."""

    def fetch_rates(self) -> Dict[str, float]:
        params = self.config.get_coingecko_params()
        data = self._make_request(self.config.COINGECKO_URL, params)

        rates = {}
        base_lower = self.config.BASE_CURRENCY.lower()
        for crypto_code, gecko_id in self.config.CRYPTO_ID_MAP.items():
            if crypto_code not in self.config.CRYPTO_CURRENCIES:
                continue
            if gecko_id in data and base_lower in data[gecko_id]:
                pair_key = f"{crypto_code}_{self.config.BASE_CURRENCY}"
                rates[pair_key] = data[gecko_id][base_lower]
        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Клиент для ExchangeRate-API (требуется ключ)."""

    def fetch_rates(self) -> Dict[str, float]:
        if not self.config.EXCHANGERATE_API_KEY:
            # Если ключа нет, возвращаем пустой словарь (фиат не обновляем)
            return {}

        url = self.config.get_exchangerate_url()
        data = self._make_request(url)

        if data.get("result") != "success":
            error_type = data.get("error-type", "unknown_error")
            raise ApiRequestError(f"ExchangeRate-API error: {error_type}")

        rates = {}
        conversion_rates = data.get("conversion_rates", {})
        for currency in self.config.FIAT_CURRENCIES:
            if currency in conversion_rates:
                pair_key = f"{currency}_{self.config.BASE_CURRENCY}"
                if self.config.BASE_CURRENCY == "USD":
                    rate = (
                        1.0 / conversion_rates[currency]
                        if conversion_rates[currency] != 0
                        else 0
                    )
                else:
                    rate = conversion_rates[currency]
                rates[pair_key] = rate
        return rates
