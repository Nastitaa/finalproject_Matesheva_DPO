from abc import ABC, abstractmethod

from .exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Абстрактный базовый класс для всех валют."""

    def __init__(self, code: str, name: str):
        # Валидация
        if not isinstance(code, str) or not (2 <= len(code) <= 5) or not code.isupper():
            raise ValueError("Код валюты должен быть строкой из 2-5 заглавных букв")
        if not name or not isinstance(name, str):
            raise ValueError("Название валюты не может быть пустым")
        self._code = code
        self._name = name

    @property
    def code(self) -> str:
        return self._code

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    def get_display_info(self) -> str:
        """Возвращает строковое представление для пользователя."""
        pass


class FiatCurrency(Currency):
    """Фиатная валюта."""

    def __init__(self, code: str, name: str, issuing_country: str):
        super().__init__(code, name)
        self._issuing_country = issuing_country

    @property
    def issuing_country(self) -> str:
        return self._issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self._issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта."""

    def __init__(self, code: str, name: str, algorithm: str, market_cap: float = 0.0):
        super().__init__(code, name)
        self._algorithm = algorithm
        self._market_cap = market_cap

    @property
    def algorithm(self) -> str:
        return self._algorithm

    @property
    def market_cap(self) -> float:
        return self._market_cap

    def get_display_info(self) -> str:
        # Форматируем капитализацию в экспоненциальной форме или с суффиксами
        cap_str = f"{self._market_cap:.2e}" if self._market_cap else "unknown"
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self._algorithm}, MCAP: {cap_str})"
        )

class CurrencyRegistry:
    """Реестр поддерживаемых валют (синглтон)."""

    _instance = None
    _currencies = {}  # приватный словарь

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self._currencies = {
            "USD": FiatCurrency("USD", "US Dollar", "United States"),
            "EUR": FiatCurrency("EUR", "Euro", "Eurozone"),
            "GBP": FiatCurrency("GBP", "British Pound", "United Kingdom"),
            "RUB": FiatCurrency("RUB", "Russian Ruble", "Russia"),
            "JPY": FiatCurrency("JPY", "Japanese Yen", "Japan"),
            "CNY": FiatCurrency("CNY", "Chinese Yuan", "China"),
            "BTC": CryptoCurrency("BTC", "Bitcoin", "SHA-256", 1.12e12),
            "ETH": CryptoCurrency("ETH", "Ethereum", "Ethash", 4.5e11),
            "SOL": CryptoCurrency("SOL", "Solana", "Proof of History", 6.8e10),
            "ADA": CryptoCurrency("ADA", "Cardano", "Ouroboros", 2.3e10),
            "DOT": CryptoCurrency(
                "DOT", "Polkadot", "Nominated Proof-of-Stake", 1.2e10
            ),
        }

    def get_currency(self, code: str) -> Currency:
        code = code.upper()
        if code not in self._currencies:
            raise CurrencyNotFoundError(code)
        return self._currencies[code]

    def get_supported_codes(self) -> list[str]:
        return list(self._currencies.keys())

    def register_currency(self, currency: Currency) -> None:
        """Метод для динамического добавления валют (если потребуется)."""
        if currency.code in self._currencies:
            raise ValueError(f"Currency {currency.code} already exists")
        self._currencies[currency.code] = currency


# Замена глобальных функций на методы реестра
def get_currency(code: str) -> Currency:
    return CurrencyRegistry().get_currency(code)


def get_supported_codes() -> list[str]:
    return CurrencyRegistry().get_supported_codes()
