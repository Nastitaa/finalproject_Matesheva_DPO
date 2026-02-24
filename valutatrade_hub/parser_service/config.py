import os
from dataclasses import dataclass
from typing import Dict, Tuple

from dotenv import load_dotenv

from ..infra.settings import SettingsLoader

load_dotenv()


@dataclass
class ParserConfig:
    """Конфигурация для сервиса парсинга."""

    # API ключи (из переменных окружения)
    EXCHANGERATE_API_KEY: str = os.getenv("EXCHANGERATE_API_KEY", "")

    # Эндпоинты
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # Базовая валюта (обычно USD)
    BASE_CURRENCY: str = "USD"

    # Списки отслеживаемых валют
    FIAT_CURRENCIES: Tuple[str, ...] = ("EUR", "GBP", "RUB", "JPY", "CNY")
    CRYPTO_CURRENCIES: Tuple[str, ...] = ("BTC", "ETH", "SOL", "ADA", "DOT")

    # Маппинг кодов криптовалют на ID в CoinGecko
    CRYPTO_ID_MAP: Dict[str, str] = None

    # Параметры запросов
    REQUEST_TIMEOUT: int = 30
    REQUEST_RETRIES: int = 3
    RETRY_DELAY: float = 1.0

    # Параметры обновления
    UPDATE_INTERVAL_MINUTES: int = 5

    # Пути к файлам (будут переопределены в __post_init__)
    RATES_FILE_PATH: str = ""
    HISTORY_FILE_PATH: str = ""

    # TTL для кэша
    RATES_TTL_SECONDS: int = 300

    def __post_init__(self):
        if self.CRYPTO_ID_MAP is None:
            self.CRYPTO_ID_MAP = {
                "BTC": "bitcoin",
                "ETH": "ethereum",
                "SOL": "solana",
                "ADA": "cardano",
                "DOT": "polkadot",
            }

        # Загружаем настройки из SettingsLoader
        settings = SettingsLoader()
        data_dir = settings.get("data_dir", "data")
        self.RATES_FILE_PATH = os.path.join(data_dir, "rates.json")
        self.HISTORY_FILE_PATH = os.path.join(data_dir, "exchange_rates.json")
        self.RATES_TTL_SECONDS = settings.get("rates_ttl_seconds", 300)

        supported = settings.get("supported_currencies")
        if supported and isinstance(supported, list):
            # Разделяем на фиат и крипто
            fiat_set = {"USD", "EUR", "GBP", "RUB", "JPY", "CNY"}
            fiat = []
            crypto = []
            for code in supported:
                if code in fiat_set:
                    fiat.append(code)
                else:
                    crypto.append(code)
            if fiat:
                self.FIAT_CURRENCIES = tuple(fiat)
            if crypto:
                self.CRYPTO_CURRENCIES = tuple(crypto)

        # Переопределяем интервал обновления из SettingsLoader, если есть
        self.UPDATE_INTERVAL_MINUTES = settings.get("update_interval_minutes", 5)

        # Таймаут из SettingsLoader
        self.REQUEST_TIMEOUT = settings.get("api_timeout", 10)

        # Создаём директорию для данных
        os.makedirs(data_dir, exist_ok=True)

    @classmethod
    def from_env(cls) -> "ParserConfig":
        """
        Создаёт экземпляр конфигурации, используя переменные окружения.
        """
        return cls()

    def validate(self) -> bool:
        """Проверяет корректность конфигурации."""
        if not self.EXCHANGERATE_API_KEY:
            print(
                "Внимание: не задан EXCHANGERATE_API_KEY."
                "Фиатные курсы не будут обновляться."
            )

        # Проверка кодов валют
        currencies = self.FIAT_CURRENCIES + self.CRYPTO_CURRENCIES
        for currency in currencies:
            if not (
                currency.isalpha() and currency.isupper() and 2 <= len(currency) <= 5
            ):
                raise ValueError(f"Некорректный код валюты: {currency}")

        return True

    def get_coingecko_params(self) -> Dict[str, str]:
        """Параметры для запроса к CoinGecko."""
        crypto_ids = []
        for code in self.CRYPTO_CURRENCIES:
            if code in self.CRYPTO_ID_MAP:
                crypto_ids.append(self.CRYPTO_ID_MAP[code])
        return {
            "ids": ",".join(crypto_ids),
            "vs_currencies": self.BASE_CURRENCY.lower(),
        }

    def get_exchangerate_url(self) -> str:
        """URL для запроса к ExchangeRate-API."""
        return (
            f"{self.EXCHANGERATE_API_URL}/{self.EXCHANGERATE_API_KEY}"
            f"/latest/{self.BASE_CURRENCY}"
        )